"""Emit per-search-term salary aggregates for the HTML salary table."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Lib", "site-packages"))
import duckdb

DB = Path(os.environ.get("JET_WORKSPACE", ".")).resolve() / "projects/jobscope/jobscope.duckdb"

def main():
    rows = []
    if DB.exists():
        c = duckdb.connect(str(DB), read_only=True)
        rows = c.execute("""
          SELECT
            search_term,
            COUNT(*) FILTER (WHERE salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL) AS n_with_salary,
            ROUND(MIN(salary_min_lpa), 1) AS min_lpa,
            ROUND(AVG((COALESCE(salary_min_lpa, salary_max_lpa) + COALESCE(salary_max_lpa, salary_min_lpa)) / 2.0), 1) AS mid_lpa,
            ROUND(MAX(salary_max_lpa), 1) AS max_lpa
          FROM jobs
          WHERE salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL
          GROUP BY search_term
          ORDER BY mid_lpa DESC NULLS LAST
        """).fetchall()
        c.close()
    sys.stdout.write(json.dumps({
        "rows": [
            {"term": r[0], "n": r[1], "min": r[2], "mid": r[3], "max": r[4]}
            for r in rows
        ],
        "expected": 12.0,
    }))

if __name__ == "__main__":
    main()
