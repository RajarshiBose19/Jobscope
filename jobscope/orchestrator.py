"""Main loop: search → for each listing → extract → analyze → snapshot → popup → record → next."""
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
from jobscope.decision.popup import ask_decision
from jobscope.profile.normalize import load_profile, sync_profile_to_db
from jobscope.scraper.applied_detector import is_applied
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
            "last_updated_at": _now_iso()}

def _snapshot_analyzing(base: dict, job: dict) -> dict:
    out = dict(base)
    out.update({"state": "analyzing", "job_id": job["job_id"],
                "title": job.get("title"), "company": job.get("company"),
                "last_updated_at": _now_iso()})
    return out

def _snapshot_analyzed(base: dict, job: dict, parsed_dict: dict, stats: dict) -> dict:
    out = dict(base)
    out.update({"state": "analyzed", "job_id": job["job_id"],
                "title": job.get("title"), "company": job.get("company"),
                "analysis": parsed_dict, "stats": stats,
                "last_updated_at": _now_iso()})
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

    conn = open_rw(config.DB_PATH)
    init_schema(conn)
    repo.seed_skills_canonical(conn)
    profile = load_profile(config.PROFILE_PATH)
    sync_profile_to_db(conn, profile)

    sid = repo.start_session(conn, config.SEARCH_TERMS, config.SEARCH_LOCATION)
    write_snapshot(config.SNAPSHOT_PATH, idle_payload(session_id=sid))

    canon = [r[0] for r in conn.execute("SELECT skill_canonical FROM skills_canonical").fetchall()]
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
            for n, (job_id, jd_url, page, pos) in enumerate(iter_listings(driver), start=1):
                if quit_requested: break
                base = _snapshot_loading(sid, term, page, pos)
                write_snapshot(config.SNAPSHOT_PATH, base)

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
                repo.mark_job_status(conn, job_id, "analyzed")

                stats = _gather_stats(conn)
                write_snapshot(config.SNAPSHOT_PATH,
                               _snapshot_analyzed(base, job, parsed.model_dump(), stats))

                decision = ask_decision(
                    title=job.get("title") or "Untitled",
                    company=job.get("company") or "Unknown",
                    fit_score=parsed.fit_score,
                    recommendation=parsed.recommendation,
                )
                if decision is None or decision == "quit":
                    quit_requested = True
                    break

                repo.record_decision(conn, job_id=job_id, session_id=sid,
                                     decision=decision, source="user")
                if decision != "apply" and is_applied(driver):
                    repo.record_decision(conn, job_id=job_id, session_id=sid,
                                         decision="apply", source="auto_detected_applied")

                write_snapshot(config.SNAPSHOT_PATH,
                               _snapshot_decided(base, job_id, decision))

                if n % config.SWITCH_AFTER == 0:
                    log.info("switch_term", extra={"after_n": n})
                    break

        repo.end_session(conn, sid, "user_quit" if quit_requested else "completed")
        write_snapshot(config.SNAPSHOT_PATH, _snapshot_stopped(sid, _gather_stats(conn)))
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
    """Tk popup that blocks while the user solves a captcha/2FA in the browser."""
    import tkinter as tk
    root = tk.Tk(); root.title("JobScope — verification required")
    root.geometry("420x140"); root.attributes("-topmost", True)
    tk.Label(root, text="LinkedIn shows a verification step.\n"
                        "Solve it in the browser, then click OK.",
             font=("Segoe UI", 10), justify="left").pack(padx=16, pady=16)
    tk.Button(root, text="OK", width=12, command=root.destroy).pack(pady=8)
    root.mainloop()
