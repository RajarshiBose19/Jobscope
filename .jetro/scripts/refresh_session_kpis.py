"""Query v_current_session_stats; emit a small KPI payload."""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Lib", "site-packages"))
import duckdb

WS = Path(os.environ.get("JET_WORKSPACE", ".")).resolve()
DB = WS / "projects" / "jobscope" / "jobscope.duckdb"

def main():
    out = {"_meta": {"computed_at": datetime.now(timezone.utc).isoformat()}}
    if not DB.exists():
        out.update({"evaluated":0,"applied":0,"skipped":0,"bookmarked":0,"avg_fit":None})
        sys.stdout.write(json.dumps(out)); return
    c = duckdb.connect(str(DB), read_only=True)
    try:
        row = c.execute("SELECT jobs_evaluated, applied, skipped, bookmarked, avg_fit "
                        "FROM v_current_session_stats").fetchone()
        if row:
            out.update({"evaluated":row[0] or 0, "applied":row[1] or 0,
                        "skipped":row[2] or 0, "bookmarked":row[3] or 0,
                        "avg_fit": float(row[4]) if row[4] is not None else None})
        else:
            out.update({"evaluated":0,"applied":0,"skipped":0,"bookmarked":0,"avg_fit":None})
    finally:
        c.close()
    sys.stdout.write(json.dumps(out))

if __name__ == "__main__":
    main()
