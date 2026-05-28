from __future__ import annotations
import json
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional
import duckdb
from jobscope import config
from jobscope.ai.analyzer import analyze
from jobscope.ai.client import GeminiClient, AnalysisFailure
from jobscope.db import repo
from jobscope.db.connection import open_rw, init_schema
from jobscope.decision.popup import ask_decision, ask_yes_no, ask_acknowledge
from jobscope.profile.normalize import load_profile, sync_profile_to_db
from jobscope.scraper.applied_detector import is_applied
from jobscope.scraper.apply import (
    click_apply_button, click_save_button, is_easy_apply,
    wait_easy_apply_resolution,
)
from jobscope.scraper.browser import new_driver, quit_driver
from jobscope.scraper.extract import extract_job_details
from jobscope.scraper.listing import iter_listings
from jobscope.scraper.login import login, LoginFailure
from jobscope.scraper.search import navigate_to_search
from jobscope.state.snapshot import write_snapshot, idle_payload
from jobscope.utils.logging import get_logger, configure_logging

log = get_logger("orchestrator")

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def _snapshot_loading(session_id: str, search_term: str, page: int, pos: int) -> dict:
    return {"state": "loading", "session_id": session_id,
            "search_term": search_term, "page": page, "position_on_page": pos,
            "user_experience_years": config.EXPERIENCE_YEARS,
            "last_updated_at": _now_iso()}

def _snapshot_analyzing(base: dict, job: dict) -> dict:
    out = dict(base)
    out.update({"state": "analyzing", "job_id": job["job_id"],
                "title": job.get("title"), "company": job.get("company"),
                "last_updated_at": _now_iso()})
    return out

def _snapshot_analyzed(base: dict, job: dict, parsed_dict: dict, stats: dict,
                       user_skills: list[str] | None = None) -> dict:
    out = dict(base)
    out.update({
        "state": "analyzed",
        "job_id": job["job_id"],
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "work_style": job.get("work_style"),
        "posted_relative": job.get("posted_relative"),
        "experience_min": job.get("experience_min"),
        "experience_max": job.get("experience_max"),
        "salary_min_lpa": job.get("salary_min_lpa"),
        "salary_max_lpa": job.get("salary_max_lpa"),
        "analysis": parsed_dict,
        "stats": stats,
        "user_skills": user_skills or [],
        "user_experience_years": config.EXPERIENCE_YEARS,
        "last_updated_at": _now_iso(),
    })
    return out

def _snapshot_error(base: dict, job_id: str, kind: str, message: str) -> dict:
    out = dict(base)
    out.update({"state": "error", "job_id": job_id,
                "error": {"kind": kind, "message": message},
                "last_updated_at": _now_iso()})
    return out

def _snapshot_decided(base: dict, job_id: str, decision: str) -> dict:
    out = dict(base)
    out.update({"state": "decided", "job_id": job_id,
                "last_decision": decision, "last_updated_at": _now_iso()})
    return out

def _snapshot_stopped(session_id: str, summary: dict) -> dict:
    return {"state": "stopped", "session_id": session_id,
            "session_summary": summary, "last_updated_at": _now_iso()}

def _gather_stats(conn: duckdb.DuckDBPyConnection) -> dict:
    row = conn.execute(
        "SELECT jobs_evaluated, applied, skipped, bookmarked, avg_fit "
        "FROM v_current_session_stats"
    ).fetchone()
    if not row:
        return {"evaluated": 0, "applied": 0, "skipped": 0, "bookmarked": 0, "avg_fit": None}
    return {"evaluated": row[0] or 0, "applied": row[1] or 0,
            "skipped": row[2] or 0, "bookmarked": row[3] or 0,
            "avg_fit": float(row[4]) if row[4] is not None else None}

def _dump_aggregates(conn: duckdb.DuckDBPyConnection) -> None:
    s = _gather_stats(conn)
    write_snapshot(config.AGG_SESSION_KPIS_PATH, s)

    rows = conn.execute("""
        SELECT display_name, jobs_asking, jobs_where_missing
        FROM v_skill_gaps
        WHERE jobs_where_missing > 0
        ORDER BY jobs_where_missing DESC LIMIT 15
    """).fetchall()
    write_snapshot(config.AGG_SKILL_GAPS_PATH, {"rows": [
        {"skill": r[0], "asking": r[1], "missing": r[2]} for r in rows
    ]})

    buckets = [0] * 10
    for (score,) in conn.execute(
        "SELECT fit_score FROM v_job_analysis WHERE fit_score IS NOT NULL"
    ).fetchall():
        buckets[min(int(score) // 10, 9)] += 1
    labels = [f"{i*10}-{i*10+9 if i<9 else 100}" for i in range(10)]
    write_snapshot(config.AGG_FIT_DISTRIBUTION_PATH, {
        "buckets": [{"label": l, "count": n} for l, n in zip(labels, buckets)],
        "total": sum(buckets),
    })

    exp_ceiling: float | None = None
    if config.EXPERIENCE_BUFFER_YEARS is not None:
        try:
            exp_ceiling = float(config.EXPERIENCE_YEARS) + float(config.EXPERIENCE_BUFFER_YEARS)
        except Exception:
            exp_ceiling = None

    if exp_ceiling is not None:
        sal_rows = conn.execute("""
            SELECT
              search_term,
              COUNT(*) FILTER (WHERE salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL) AS n_with_salary,
              ROUND(MIN(salary_min_lpa), 1) AS min_lpa,
              ROUND(AVG((COALESCE(salary_min_lpa, salary_max_lpa) + COALESCE(salary_max_lpa, salary_min_lpa)) / 2.0), 1) AS mid_lpa,
              ROUND(MAX(salary_max_lpa), 1) AS max_lpa
            FROM jobs
            WHERE (salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL)
              AND (experience_min IS NULL OR experience_min <= ?)
            GROUP BY search_term
            ORDER BY mid_lpa DESC NULLS LAST
        """, [exp_ceiling]).fetchall()
    else:
        sal_rows = conn.execute("""
            SELECT
              search_term,
              COUNT(*) FILTER (WHERE salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL) AS n_with_salary,
              ROUND(MIN(salary_min_lpa), 1) AS min_lpa,
              ROUND(AVG((COALESCE(salary_min_lpa, salary_max_lpa) + COALESCE(salary_max_lpa, salary_min_lpa)) / 2.0), 1) AS mid_lpa,
              ROUND(MAX(salary_max_lpa), 1) AS max_lpa
            FROM jobs
            WHERE salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL
            GROUP BY search_term
            ORDER BY mid_lpa DESC NULLS LAST
        """).fetchall()
    write_snapshot(config.AGG_SALARY_MAP_PATH, {
        "rows": [
            {"term": r[0], "n": r[1], "min": r[2], "mid": r[3], "max": r[4]}
            for r in sal_rows
        ],
        "expected": float(config.EXPECTED_CTC_LPA),
        "yoe_ceiling": exp_ceiling,
    })

    if exp_ceiling is not None:
        st_rows = conn.execute("""
            SELECT j.search_term,
                   COUNT(*) AS jobs_seen,
                   ROUND(AVG(a.fit_score), 1) AS avg_fit,
                   COUNT(*) FILTER (WHERE d.decision IN ('apply', 'apply_external_submitted')) AS applied,
                   COUNT(*) FILTER (WHERE d.decision = 'skip') AS skipped,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE d.decision IN ('apply', 'apply_external_submitted'))
                         / NULLIF(COUNT(*), 0), 1) AS apply_rate_pct
            FROM jobs j
            LEFT JOIN v_job_analysis a USING (job_id)
            LEFT JOIN LATERAL (
              SELECT decision FROM decisions
              WHERE job_id = j.job_id ORDER BY decided_at DESC LIMIT 1
            ) d ON true
            WHERE (j.experience_min IS NULL OR j.experience_min <= ?)
            GROUP BY j.search_term
            ORDER BY avg_fit DESC NULLS LAST
        """, [exp_ceiling]).fetchall()
    else:
        st_rows = conn.execute("""
            SELECT search_term, jobs_seen, avg_fit, applied, skipped, apply_rate_pct
            FROM v_search_term_report
        """).fetchall()
    write_snapshot(config.AGG_SEARCH_TERM_REPORT_PATH, {
        "rows": [
            {"term": r[0], "seen": r[1], "avg_fit": r[2], "applied": r[3],
             "skipped": r[4], "apply_rate": r[5]}
            for r in st_rows
        ],
        "yoe_ceiling": exp_ceiling,
    })

def _archive_stale_snapshot() -> None:
    if not config.SNAPSHOT_PATH.exists():
        return
    config.CRASHED_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    target = config.CRASHED_DIR / f"snapshot-{ts}.json"
    config.SNAPSHOT_PATH.replace(target)
    log.info("archived_stale_snapshot", extra={"target": str(target)})

def run() -> int:
    config.ensure_dirs()
    configure_logging(config.LOG_PATH)
    log.info("bot_start")

    _archive_stale_snapshot()
    write_snapshot(config.AGG_SESSION_KPIS_PATH, {
        "evaluated": 0, "applied": 0, "skipped": 0, "bookmarked": 0,
        "avg_fit": None,
    })

    conn = open_rw(config.DB_PATH)
    init_schema(conn)
    repo.seed_skills_canonical(conn)
    profile = load_profile(config.PROFILE_PATH)
    sync_profile_to_db(conn, profile)

    sid = repo.start_session(conn, config.SEARCH_TERMS, config.SEARCH_LOCATION)
    write_snapshot(config.SNAPSHOT_PATH, idle_payload(session_id=sid))
    _dump_aggregates(conn)

    canon = [r[0] for r in conn.execute("SELECT skill_canonical FROM skills_canonical").fetchall()]
    user_skills_canonical = [
        r[0] for r in conn.execute("SELECT skill_canonical FROM user_skills").fetchall()
    ]
    log.info("user_skills_loaded", extra={"count": len(user_skills_canonical)})
    gem = GeminiClient(keys=config.GEMINI_API_KEYS, model=config.GEMINI_MODEL)

    driver = new_driver()
    try:
        login(driver, on_verification=lambda: _wait_for_user_verify())
    except LoginFailure as e:
        log.error("login_failed", extra={"err": str(e)})
        write_snapshot(config.SNAPSHOT_PATH,
                       _snapshot_error({"session_id": sid}, "", "login", str(e)))
        quit_driver(driver); conn.close()
        return 2

    quit_requested = False
    def _on_sigint(*_):
        nonlocal quit_requested
        quit_requested = True
        log.warning("sigint_received")
    signal.signal(signal.SIGINT, _on_sigint)

    try:
        for term in config.SEARCH_TERMS:
            if quit_requested: break
            navigate_to_search(driver, term)
            applies_in_term = 0
            popups_in_term = 0
            for n, card in enumerate(iter_listings(driver), start=1):
                if quit_requested: break
                job_id = card["job_id"]
                jd_url = card["jd_url"]
                page = card["page"]
                pos = card["position_on_page"]
                base = _snapshot_loading(sid, term, page, pos)
                write_snapshot(config.SNAPSHOT_PATH, base)

                if not card["clicked"]:
                    if card["already_applied"]:
                        _stub_upsert_job(conn, sid, term, job_id, jd_url,
                                         card["company_hint"])
                        if not repo.has_apply_decision(conn, job_id):
                            repo.record_decision(
                                conn, job_id=job_id, session_id=sid,
                                decision="apply", source="auto_detected_applied",
                                notes="card_footer_badge",
                            )
                        log.info("auto_skip_already_applied", extra={"job_id": job_id})
                    else:
                        _stub_upsert_job(conn, sid, term, job_id, jd_url,
                                         card["company_hint"])
                        repo.record_decision(
                            conn, job_id=job_id, session_id=sid,
                            decision="skip", source="auto_pre_filter",
                            notes=f"blacklisted_company: {card['company_hint']}",
                        )
                        log.info("auto_skip_blacklisted_company",
                                 extra={"job_id": job_id, "company": card["company_hint"]})
                    _dump_aggregates(conn)
                    continue

                if repo.recent_decision_exists(conn, job_id, config.RECENT_ANALYSIS_DAYS):
                    log.info("auto_skip_recently_analyzed",
                             extra={"job_id": job_id, "days": config.RECENT_ANALYSIS_DAYS})
                    continue

                job = extract_job_details(driver, job_id=job_id, jd_url=jd_url)
                job.update({"session_id": sid,
                            "scraped_at": datetime.now(timezone.utc),
                            "search_term": term})
                repo.upsert_job(conn, job)
                repo.touch_current_job(conn, job_id)

                if not job.get("jd_full_text"):
                    repo.mark_job_status(conn, job_id, "failed", "jd_empty")
                    write_snapshot(config.SNAPSHOT_PATH,
                                   _snapshot_error(base, job_id, "jd_empty", "no JD text"))
                    continue

                bad_hit = _jd_bad_word(job.get("jd_full_text") or "")
                if bad_hit:
                    repo.mark_job_status(conn, job_id, "skipped_pre_analysis",
                                         f"jd_bad_word: {bad_hit}")
                    repo.record_decision(
                        conn, job_id=job_id, session_id=sid,
                        decision="skip", source="auto_pre_filter",
                        notes=f"jd_bad_word: {bad_hit}",
                    )
                    log.info("auto_skip_jd_bad_word",
                             extra={"job_id": job_id, "word": bad_hit})
                    _dump_aggregates(conn)
                    continue

                exp_skip_reason = _experience_threshold_reason(
                    job.get("experience_min"), job.get("experience_max")
                )
                if exp_skip_reason:
                    repo.mark_job_status(conn, job_id, "skipped_pre_analysis",
                                         exp_skip_reason)
                    repo.record_decision(
                        conn, job_id=job_id, session_id=sid,
                        decision="skip", source="auto_pre_filter",
                        notes=exp_skip_reason,
                    )
                    log.info("auto_skip_experience_too_high",
                             extra={"job_id": job_id, "reason": exp_skip_reason})
                    _dump_aggregates(conn)
                    continue

                write_snapshot(config.SNAPSHOT_PATH, _snapshot_analyzing(base, job))
                try:
                    parsed, raw, latency = analyze(gem, profile=profile,
                                                   skills_canonical=canon, job=job)
                except AnalysisFailure as e:
                    repo.mark_job_status(conn, job_id, "failed", str(e))
                    write_snapshot(config.SNAPSHOT_PATH,
                                   _snapshot_error(base, job_id, "analysis", str(e)))
                    continue

                repo.insert_analysis(conn, job_id=job_id,
                                     prompt_version=config.PROMPT_VERSION,
                                     model_name=config.GEMINI_MODEL,
                                     latency_ms=latency,
                                     parsed=parsed.model_dump(),
                                     raw_json=raw)
                repo.replace_job_skills(conn, job_id,
                    [{"canonical": s.canonical, "as_written": s.as_written, "kind": s.kind}
                     for s in parsed.skills])
                repo.fill_salary_if_missing(conn, job_id,
                                            parsed.salary_min_lpa,
                                            parsed.salary_max_lpa)
                repo.mark_job_status(conn, job_id, "analyzed")

                stats = _gather_stats(conn)
                write_snapshot(config.SNAPSHOT_PATH,
                               _snapshot_analyzed(base, job, parsed.model_dump(), stats,
                                                  user_skills=user_skills_canonical))

                decision = ask_decision(
                    title=job.get("title") or "Untitled",
                    company=job.get("company") or "Unknown",
                    fit_score=parsed.fit_score,
                    recommendation=parsed.recommendation,
                )
                if decision is None or decision == "quit":
                    quit_requested = True
                    break

                final_decision = _handle_decision(driver, decision)

                repo.record_decision(conn, job_id=job_id, session_id=sid,
                                     decision=final_decision, source="user")
                if final_decision not in ("apply", "apply_external_submitted") and is_applied(driver):
                    repo.record_decision(conn, job_id=job_id, session_id=sid,
                                         decision="apply", source="auto_detected_applied")

                write_snapshot(config.SNAPSHOT_PATH,
                               _snapshot_decided(base, job_id, final_decision))
                _dump_aggregates(conn)

                popups_in_term += 1
                if final_decision in ("apply", "apply_external_submitted"):
                    applies_in_term += 1
                if applies_in_term >= config.SWITCH_AFTER:
                    log.info("switch_term",
                             extra={"reason": "apply_threshold",
                                    "applies": applies_in_term,
                                    "popups": popups_in_term})
                    break
                if popups_in_term >= config.MAX_POPUPS_PER_TERM:
                    log.warning("switch_term",
                                extra={"reason": "popup_safety_cap",
                                       "applies": applies_in_term,
                                       "popups": popups_in_term})
                    break

        repo.end_session(conn, sid, "user_quit" if quit_requested else "completed")
        write_snapshot(config.SNAPSHOT_PATH, _snapshot_stopped(sid, _gather_stats(conn)))
        _dump_aggregates(conn)
        return 0
    except Exception as e:
        log.exception("orchestrator_crash")
        repo.end_session(conn, sid, "crashed")
        write_snapshot(config.SNAPSHOT_PATH,
                       _snapshot_error({"session_id": sid}, "", "crash", str(e)))
        return 1
    finally:
        quit_driver(driver)
        conn.close()

def _wait_for_user_verify() -> None:
    import tkinter as tk
    root = tk.Tk(); root.title("JobScope — verification required")
    root.geometry("420x140"); root.attributes("-topmost", True)
    tk.Label(root, text="LinkedIn shows a verification step.\n"
                        "Solve it in the browser, then click OK.",
             font=("Segoe UI", 10), justify="left").pack(padx=16, pady=16)
    tk.Button(root, text="OK", width=12, command=root.destroy).pack(pady=8)
    root.mainloop()


def _stub_upsert_job(conn, session_id: str, search_term: str,
                     job_id: str, jd_url: str, company_hint: str) -> None:
    repo.upsert_job(conn, {
        "job_id": job_id,
        "session_id": session_id,
        "scraped_at": datetime.now(timezone.utc),
        "search_term": search_term,
        "title": None,
        "company": company_hint or None,
        "location": None,
        "work_style": None,
        "posted_relative": None,
        "experience_text": None,
        "experience_min": None,
        "experience_max": None,
        "salary_min_lpa": None,
        "salary_max_lpa": None,
        "salary_text": None,
        "jd_full_text": None,
        "jd_url": jd_url,
    })
    repo.mark_job_status(conn, job_id, "pre_skipped", None)


def _jd_bad_word(jd_text: str) -> str | None:
    if not jd_text or not config.JD_BAD_WORDS:
        return None
    haystack = jd_text.lower()
    for w in config.JD_BAD_WORDS:
        if w and w.lower() in haystack:
            return w
    return None


def _experience_threshold_reason(years_min, years_max) -> str | None:
    if config.EXPERIENCE_BUFFER_YEARS is None:
        log.info("exp_filter_disabled")
        return None
    try:
        ceiling = float(config.EXPERIENCE_YEARS) + float(config.EXPERIENCE_BUFFER_YEARS)
    except Exception:
        log.warning("exp_filter_bad_config")
        return None
    candidate = years_min if years_min is not None else years_max
    if candidate is None:
        log.info("exp_filter_no_years_extracted",
                 extra={"ceiling": ceiling, "min": years_min, "max": years_max})
        return None
    try:
        cand = float(candidate)
    except Exception:
        return None
    log.info("exp_filter_check",
             extra={"jd_min": years_min, "jd_max": years_max,
                    "candidate": cand, "ceiling": ceiling,
                    "will_skip": cand > ceiling})
    if cand > ceiling:
        return f"experience_too_high: jd_min={cand}, user_ceiling={ceiling}"
    return None


def _handle_decision(driver, decision: str) -> str:
    if decision == "skip":
        return "skip"

    if decision == "bookmark":
        if click_save_button(driver):
            log.info("linkedin_save_clicked")
        else:
            log.warning("linkedin_save_click_failed")
        return "bookmark"

    if decision == "apply":
        if is_applied(driver):
            log.info("apply_skipped_already_applied")
            return "apply"
        easy = is_easy_apply(driver)
        if not click_apply_button(driver):
            log.warning("apply_button_unavailable")
            return "apply_unavailable"
        log.info("apply_clicked", extra={"easy_apply": easy})
        if easy:
            outcome = wait_easy_apply_resolution(driver)
            log.info("easy_apply_outcome", extra={"outcome": outcome})
            if outcome == "submitted":
                return "apply"
            confirmed = ask_yes_no(
                title="JobScope - confirm application",
                message=("JobScope didn't see a confirmation badge for this "
                         "Easy Apply. Did you actually submit the "
                         "application?"),
                yes_text="Yes, I submitted",
                no_text="No, I cancelled",
            )
            return "apply" if confirmed else "apply_abandoned"
        submitted = ask_yes_no(
            title="JobScope - external application",
            message=("This job uses an external application page (opened in "
                     "a new tab).\n\nDid you complete and submit the "
                     "application there?"),
            yes_text="Yes, submitted",
            no_text="No / cancelled",
        )
        return "apply_external_submitted" if submitted else "apply_external_not_submitted"

    return decision
