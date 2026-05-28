from __future__ import annotations
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import duckdb
from jobscope.utils.ids import new_session_id, new_uuid

SEED_CSV = Path(__file__).parent / "seed_skills.csv"

def seed_skills_canonical(conn: duckdb.DuckDBPyConnection) -> int:
    with SEED_CSV.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    n = 0
    for r in rows:
        conn.execute("""
            INSERT INTO skills_canonical(skill_canonical, display_name, category, aliases)
            VALUES (?, ?, ?, ?::JSON)
            ON CONFLICT(skill_canonical) DO UPDATE SET
              display_name = excluded.display_name,
              category     = excluded.category,
              aliases      = excluded.aliases
        """, [r["skill_canonical"], r["display_name"], r["category"], r["aliases"]])
        n += 1
    return n

def start_session(conn, search_terms: list[str], search_location: str,
                  filters: dict | None = None) -> str:
    sid = new_session_id()
    conn.execute("""
        INSERT INTO sessions(session_id, started_at, search_terms, search_location, filters_applied)
        VALUES (?, ?, ?::JSON, ?, ?::JSON)
    """, [sid, datetime.now(timezone.utc), json.dumps(search_terms),
          search_location, json.dumps(filters or {})])
    conn.execute("""
        UPDATE session_state SET current_session_id=?, last_active_at=? WHERE id=1
    """, [sid, datetime.now(timezone.utc)])
    return sid

def end_session(conn, session_id: str, reason: str) -> None:
    conn.execute("""
        UPDATE sessions SET ended_at=?, ended_reason=? WHERE session_id=?
    """, [datetime.now(timezone.utc), reason, session_id])

def touch_current_job(conn, job_id: str) -> None:
    conn.execute("""
        UPDATE session_state SET current_job_id=?, last_active_at=? WHERE id=1
    """, [job_id, datetime.now(timezone.utc)])

def upsert_job(conn, job: dict[str, Any]) -> None:
    cols = ["job_id","session_id","scraped_at","search_term","title","company","location",
            "work_style","posted_relative","experience_text","experience_min","experience_max",
            "salary_min_lpa","salary_max_lpa","salary_text","jd_full_text","jd_url"]
    placeholders = ",".join(["?"] * len(cols))
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "job_id")
    conn.execute(f"""
        INSERT INTO jobs({",".join(cols)}) VALUES ({placeholders})
        ON CONFLICT(job_id) DO UPDATE SET {updates}
    """, [job.get(c) for c in cols])

def mark_job_status(conn, job_id: str, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE jobs SET analysis_status=?, analysis_error=? WHERE job_id=?",
        [status, error, job_id],
    )

def fill_salary_if_missing(conn, job_id: str, salary_min_lpa, salary_max_lpa) -> None:
    if salary_min_lpa is None and salary_max_lpa is None:
        return
    conn.execute("""
        UPDATE jobs
        SET salary_min_lpa = COALESCE(salary_min_lpa, ?),
            salary_max_lpa = COALESCE(salary_max_lpa, ?)
        WHERE job_id = ?
    """, [salary_min_lpa, salary_max_lpa, job_id])

def insert_analysis(conn, *, job_id: str, prompt_version: str, model_name: str,
                    latency_ms: int, parsed: dict, raw_json: str) -> str:
    aid = new_uuid()
    conn.execute("""
        INSERT INTO analyses(analysis_id, job_id, prompt_version, model_name,
                             analyzed_at, latency_ms, fit_score, experience_verdict,
                             jd_quality, red_flags, recommendation, resume_tailoring,
                             raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?, ?, ?::JSON)
    """, [aid, job_id, prompt_version, model_name,
          datetime.now(timezone.utc), latency_ms,
          parsed["fit_score"], parsed["experience_verdict"], parsed["jd_quality"],
          json.dumps(parsed.get("red_flags", [])),
          parsed["recommendation"], parsed["resume_tailoring"], raw_json])
    return aid

def replace_job_skills(conn, job_id: str, skills: list[dict]) -> None:
    conn.execute("DELETE FROM job_skills WHERE job_id=?", [job_id])
    for s in skills:
        conn.execute("""
            INSERT INTO job_skills(job_id, skill_canonical, skill_as_written, kind)
            VALUES (?, ?, ?, ?)
            ON CONFLICT DO NOTHING
        """, [job_id, s["canonical"], s["as_written"], s["kind"]])

def record_decision(conn, *, job_id: str, session_id: str, decision: str,
                    source: str, notes: str | None = None) -> str:
    did = new_uuid()
    conn.execute("""
        INSERT INTO decisions(decision_id, job_id, session_id, decided_at,
                              decision, source, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [did, job_id, session_id, datetime.now(timezone.utc), decision, source, notes])
    return did

def recent_decision_exists(conn, job_id: str, days: int) -> bool:
    row = conn.execute("""
        SELECT 1 FROM decisions
        WHERE job_id = ?
          AND decided_at >= (CURRENT_TIMESTAMP - INTERVAL (?) DAY)
        LIMIT 1
    """, [job_id, days]).fetchone()
    return row is not None

def has_apply_decision(conn, job_id: str) -> bool:
    row = conn.execute("""
        SELECT 1 FROM decisions
        WHERE job_id = ?
          AND decision IN ('apply', 'apply_external_submitted')
        LIMIT 1
    """, [job_id]).fetchone()
    return row is not None

def upsert_user_profile(conn, profile: dict) -> None:
    conn.execute("""
        INSERT INTO user_profile(id, full_name, current_role, current_company,
                                 experience_years, current_ctc_lpa, expected_ctc_lpa,
                                 current_location, willing_locations, certifications,
                                 updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?::JSON, ?)
        ON CONFLICT(id) DO UPDATE SET
          full_name=excluded.full_name, current_role=excluded.current_role,
          current_company=excluded.current_company,
          experience_years=excluded.experience_years,
          current_ctc_lpa=excluded.current_ctc_lpa,
          expected_ctc_lpa=excluded.expected_ctc_lpa,
          current_location=excluded.current_location,
          willing_locations=excluded.willing_locations,
          certifications=excluded.certifications,
          updated_at=excluded.updated_at
    """, [profile.get("full_name"), profile.get("current_role"),
          profile.get("current_company"), profile.get("experience_years"),
          profile.get("current_ctc_lpa"), profile.get("expected_ctc_lpa"),
          profile.get("current_location"),
          json.dumps(profile.get("willing_locations", [])),
          json.dumps(profile.get("certifications", [])),
          datetime.now(timezone.utc)])

def replace_user_skills(conn, skills: list[dict]) -> None:
    conn.execute("DELETE FROM user_skills")
    for s in skills:
        conn.execute("""
            INSERT INTO user_skills(skill_canonical, proficiency, years)
            VALUES (?, ?, ?)
        """, [s["skill_canonical"], s.get("proficiency"), s.get("years")])
