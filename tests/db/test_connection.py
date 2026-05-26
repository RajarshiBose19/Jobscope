from jobscope.db.connection import open_rw, open_ro, init_schema

def test_init_schema_creates_tables(tmp_path):
    db_path = tmp_path / "x.duckdb"
    conn = open_rw(db_path)
    init_schema(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()}
    assert {"jobs","analyses","job_skills","skills_canonical","user_skills",
            "user_profile","decisions","sessions","session_state"} <= tables
    conn.close()

def test_init_schema_creates_views(tmp_path):
    db_path = tmp_path / "y.duckdb"
    conn = open_rw(db_path)
    init_schema(conn)
    views = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='main' AND table_type='VIEW'"
    ).fetchall()}
    assert {"v_job_analysis","v_skill_gaps","v_search_term_report",
            "v_current_session_stats"} <= views
    conn.close()

def test_ro_connection_cannot_write(tmp_path):
    db_path = tmp_path / "z.duckdb"
    rw = open_rw(db_path)
    init_schema(rw)
    rw.close()
    ro = open_ro(db_path)
    import pytest
    with pytest.raises(Exception):
        ro.execute("INSERT INTO sessions(session_id, started_at) VALUES ('s', now())")
    ro.close()
