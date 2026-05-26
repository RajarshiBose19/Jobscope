from pathlib import Path
from jobscope.state.snapshot import write_snapshot, read_snapshot, idle_payload

def test_write_then_read(tmp_path):
    p = tmp_path / "cur.json"
    write_snapshot(p, {"state": "analyzing", "job_id": "x"})
    out = read_snapshot(p)
    assert out["state"] == "analyzing"
    assert out["job_id"] == "x"
    assert "last_updated_at" in out

def test_read_missing_returns_idle(tmp_path):
    p = tmp_path / "missing.json"
    out = read_snapshot(p)
    assert out["state"] == "idle"

def test_atomic_no_partial(tmp_path):
    p = tmp_path / "cur.json"
    write_snapshot(p, idle_payload(session_id="s"))
    assert not (tmp_path / "cur.json.tmp").exists()

def test_idle_payload_contains_required_keys():
    p = idle_payload(session_id="s1")
    assert p["state"] == "idle"
    assert p["session_id"] == "s1"
