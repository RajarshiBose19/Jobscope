from pathlib import Path
from jobscope.profile.normalize import load_profile, sync_profile_to_db
from jobscope.db.connection import open_rw, init_schema

def test_load_profile_returns_dict(tmp_path):
    p = load_profile(Path("projects/jobscope/profile.json"))
    assert p["full_name"] == "Rajarshi Bose"
    assert len(p["skills"]) > 20

def test_sync_profile_to_db_populates_tables(tmp_path):
    p = load_profile(Path("projects/jobscope/profile.json"))
    c = open_rw(tmp_path / "p.duckdb"); init_schema(c)
    sync_profile_to_db(c, p)
    name = c.execute("SELECT full_name FROM user_profile WHERE id=1").fetchone()[0]
    assert name == "Rajarshi Bose"
    n = c.execute("SELECT COUNT(*) FROM user_skills").fetchone()[0]
    assert n == len(p["skills"])
