from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path
import click
from jobscope import config
from jobscope.db.connection import open_rw, init_schema
from jobscope.db import repo
from jobscope.profile.normalize import load_profile, sync_profile_to_db
from jobscope.state.snapshot import write_snapshot, idle_payload
from jobscope.utils.logging import configure_logging, get_logger

log = get_logger("cli")

@click.group()
def main():
    """JobScope command line."""
    config.ensure_dirs()
    configure_logging(config.LOG_PATH)

@main.command()
def run():
    """Start the bot: log in, iterate jobs, analyze, prompt for decisions."""
    from jobscope.orchestrator import run as run_bot
    sys.exit(run_bot())

@main.command("seed-skills")
def seed_skills():
    """Load (or refresh) skills_canonical from seed_skills.csv."""
    conn = open_rw(config.DB_PATH); init_schema(conn)
    n = repo.seed_skills_canonical(conn)
    click.echo(f"Loaded {n} canonical skills.")
    conn.close()

@main.command("parse-resume")
def parse_resume():
    """Verify resume PDF parses; load profile.json into DB."""
    from jobscope.profile.parse_resume import extract_text
    text = extract_text(config.RESUME_PDF)
    click.echo(f"Resume parsed: {len(text)} chars.")
    conn = open_rw(config.DB_PATH); init_schema(conn)
    p = load_profile(config.PROFILE_PATH)
    sync_profile_to_db(conn, p)
    click.echo(f"Synced profile + {len(p['skills'])} user skills to DB.")
    conn.close()

@main.command("clear-live")
def clear_live():
    """Reset current_job.json and all aggregate JSON snapshots to empty."""
    write_snapshot(config.SNAPSHOT_PATH, idle_payload())
    empty_aggregates = {
        config.AGG_SESSION_KPIS_PATH: {
            "evaluated": 0, "applied": 0, "skipped": 0, "bookmarked": 0,
            "avg_fit": None,
        },
        config.AGG_SKILL_GAPS_PATH: {"rows": []},
        config.AGG_FIT_DISTRIBUTION_PATH: {"buckets": [], "total": 0},
        config.AGG_SALARY_MAP_PATH: {"rows": [], "expected": float(config.EXPECTED_CTC_LPA)},
        config.AGG_SEARCH_TERM_REPORT_PATH: {"rows": []},
    }
    for path, payload in empty_aggregates.items():
        write_snapshot(path, payload)
    click.echo(f"Cleared snapshot + {len(empty_aggregates)} aggregate files in {config.PROJECT_ROOT / 'state'}")

@main.command()
@click.option("--confirm", is_flag=True, required=True,
              help="Required to confirm destructive wipe")
def reset(confirm: bool):
    """Archive the DB and recreate empty tables."""
    if config.DB_PATH.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        bak = config.DB_PATH.with_name(f"{config.DB_PATH.name}.bak-{ts}")
        config.DB_PATH.replace(bak)
        click.echo(f"Archived {config.DB_PATH} -> {bak.name}")
    if config.SNAPSHOT_PATH.exists():
        config.SNAPSHOT_PATH.unlink()
    conn = open_rw(config.DB_PATH); init_schema(conn)
    repo.seed_skills_canonical(conn)
    conn.close()
    click.echo("Fresh DB created with seeded skills.")

@main.command("backfill-salary")
def backfill_salary():
    """Re-parse every existing job's JD and saved Gemini response to fill missing salary columns."""
    import json as _json
    from jobscope.scraper.extract import extract_salary_lpa
    conn = open_rw(config.DB_PATH); init_schema(conn)
    try:
        rows = conn.execute("""
            SELECT j.job_id, j.jd_full_text, j.salary_min_lpa, j.salary_max_lpa
            FROM jobs j
            WHERE j.salary_min_lpa IS NULL AND j.salary_max_lpa IS NULL
        """).fetchall()
        click.echo(f"Scanning {len(rows)} jobs with no salary on file.")
        filled_jd = 0
        filled_gemini = 0
        for job_id, jd_text, _, _ in rows:
            sal_min = sal_max = None
            if jd_text:
                sal_min, sal_max, _ = extract_salary_lpa(jd_text)
            if sal_min is None:
                gem_row = conn.execute("""
                    SELECT raw_response FROM analyses
                    WHERE job_id = ?
                    ORDER BY analyzed_at DESC LIMIT 1
                """, [job_id]).fetchone()
                if gem_row and gem_row[0]:
                    try:
                        raw = gem_row[0]
                        parsed = _json.loads(raw) if isinstance(raw, str) else raw
                        candidate = parsed
                        if isinstance(parsed, dict) and "fit_score" not in parsed:
                            for v in parsed.values():
                                if isinstance(v, dict) and "fit_score" in v:
                                    candidate = v
                                    break
                        if isinstance(candidate, dict):
                            g_min = candidate.get("salary_min_lpa")
                            g_max = candidate.get("salary_max_lpa")
                            if g_min is not None or g_max is not None:
                                sal_min, sal_max = g_min, g_max
                                filled_gemini += 1
                    except Exception:
                        pass
            else:
                filled_jd += 1

            if sal_min is not None or sal_max is not None:
                repo.fill_salary_if_missing(conn, job_id, sal_min, sal_max)
        click.echo(f"Backfilled {filled_jd} from JD text + {filled_gemini} from Gemini.")
        from jobscope.orchestrator import _dump_aggregates
        _dump_aggregates(conn)
        click.echo("Salary-map aggregate snapshot refreshed.")
    finally:
        conn.close()


@main.command("login-only")
def login_only():
    """Open Chrome and log in; useful to clear captcha walls before a run."""
    from jobscope.scraper.browser import new_driver, quit_driver
    from jobscope.scraper.login import login
    from jobscope.decision.popup import ask_acknowledge
    d = new_driver()
    try:
        login(d, on_verification=lambda: ask_acknowledge(
            title="JobScope - LinkedIn verification",
            message=("LinkedIn is asking for verification (captcha / 2FA / "
                     "email code).\n\nSolve it in the Chrome window, then "
                     "click Continue here."),
            button_text="Continue",
        ))
        click.echo("Logged in. Closing browser.")
    finally:
        quit_driver(d)
