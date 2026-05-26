"""CLI entry points."""
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
    """Verify resume PDF parses (sanity); load profile.json into DB."""
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
    """Reset current_job.json to idle."""
    write_snapshot(config.SNAPSHOT_PATH, idle_payload())
    click.echo(f"Cleared {config.SNAPSHOT_PATH}")

@main.command()
@click.option("--confirm", is_flag=True, required=True,
              help="Required to confirm destructive wipe")
def reset(confirm: bool):
    """Archive the DB and recreate empty tables."""
    if config.DB_PATH.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        bak = config.DB_PATH.with_name(f"{config.DB_PATH.name}.bak-{ts}")
        config.DB_PATH.replace(bak)
        click.echo(f"Archived {config.DB_PATH} → {bak.name}")
    if config.SNAPSHOT_PATH.exists():
        config.SNAPSHOT_PATH.unlink()
    conn = open_rw(config.DB_PATH); init_schema(conn)
    repo.seed_skills_canonical(conn)
    conn.close()
    click.echo("Fresh DB created with seeded skills.")

@main.command("login-only")
def login_only():
    """Open Chrome and log in; useful to clear captcha walls before a run."""
    from jobscope.scraper.browser import new_driver, quit_driver
    from jobscope.scraper.login import login
    d = new_driver()
    try:
        login(d, on_verification=lambda: input("Solve verification, then press Enter..."))
        click.echo("Logged in. Closing browser.")
    finally:
        quit_driver(d)
