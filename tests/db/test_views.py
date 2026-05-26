from datetime import datetime, timezone
from jobscope.db import repo
from jobscope.db.connection import open_rw, init_schema

def _seed(tmp_path):
    c = open_rw(tmp_path / "v.duckdb"); init_schema(c)
    repo.seed_skills_canonical(c)
    repo.replace_user_skills(c, [{"skill_canonical": "python", "proficiency": "expert", "years": 3}])
    sid = repo.start_session(c, ["AWS Engineer"], "Bengaluru")
    repo.upsert_job(c, {"job_id":"j1","session_id":sid,"scraped_at":datetime.now(timezone.utc),
                        "search_term":"AWS Engineer","title":"Sr AWS Eng","company":"Acme",
                        "location":"BLR","work_style":"Remote","posted_relative":"1d",
                        "experience_text":"3-5","experience_min":3,"experience_max":5,
                        "salary_min_lpa":None,"salary_max_lpa":None,"salary_text":None,
                        "jd_full_text":"need kubernetes","jd_url":"u"})
    repo.replace_job_skills(c, "j1", [
        {"canonical":"kubernetes","as_written":"K8s","kind":"required"},
        {"canonical":"python","as_written":"Python","kind":"required"},
    ])
    repo.insert_analysis(c, job_id="j1", prompt_version="1.0.0",
        model_name="gemini-2.5-flash-lite", latency_ms=2000,
        parsed={"fit_score":70,"experience_verdict":"in_range","jd_quality":"average",
                "red_flags":[],"recommendation":"ok","resume_tailoring":"emphasize python"},
        raw_json='{"ok":true}')
    repo.record_decision(c, job_id="j1", session_id=sid, decision="apply", source="user")
    return c, sid

def test_v_job_analysis_returns_joined_row(tmp_path):
    c, _ = _seed(tmp_path)
    row = c.execute("SELECT title, fit_score, latest_decision FROM v_job_analysis").fetchone()
    assert row == ("Sr AWS Eng", 70, "apply")

def test_v_skill_gaps_flags_missing_kubernetes(tmp_path):
    c, _ = _seed(tmp_path)
    row = c.execute(
        "SELECT jobs_where_missing FROM v_skill_gaps WHERE skill_canonical='kubernetes'"
    ).fetchone()
    assert row[0] == 1

def test_v_skill_gaps_does_not_flag_python_user_has_it(tmp_path):
    c, _ = _seed(tmp_path)
    row = c.execute(
        "SELECT jobs_where_missing FROM v_skill_gaps WHERE skill_canonical='python'"
    ).fetchone()
    assert row[0] == 0

def test_v_current_session_stats(tmp_path):
    c, _ = _seed(tmp_path)
    row = c.execute(
        "SELECT jobs_evaluated, applied, avg_fit FROM v_current_session_stats"
    ).fetchone()
    assert row == (1, 1, 70.0)
