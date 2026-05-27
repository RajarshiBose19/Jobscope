"""Emit fit-score histogram buckets (0-9, 10-19, ..., 90-100) for HTML/CSS column chart."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Lib", "site-packages"))
import duckdb

DB = Path(os.environ.get("JET_WORKSPACE", ".")).resolve() / "projects/jobscope/jobscope.duckdb"

def main():
    buckets = [0] * 10  # indices 0..9 = scores 0-9, 10-19, ..., 90-100
    if DB.exists():
        c = duckdb.connect(str(DB), read_only=True)
        for (s,) in c.execute(
            "SELECT fit_score FROM v_job_analysis WHERE fit_score IS NOT NULL"
        ).fetchall():
            buckets[min(s // 10, 9)] += 1
        c.close()
    labels = [f"{i*10}-{i*10+9 if i<9 else 100}" for i in range(10)]
    sys.stdout.write(json.dumps({
        "buckets": [{"label": l, "count": n} for l, n in zip(labels, buckets)],
        "total": sum(buckets),
    }))

if __name__ == "__main__":
    main()
