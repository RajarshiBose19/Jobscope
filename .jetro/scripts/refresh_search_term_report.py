import json, os, sys
from pathlib import Path
import duckdb
DB = Path(os.environ.get("JET_WORKSPACE",".")).resolve() / "projects/jobscope/jobscope.duckdb"
def main():
    if not DB.exists(): sys.stdout.write(json.dumps({"rows":[]})); return
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute("""
      SELECT search_term, jobs_seen, avg_fit, applied, skipped, apply_rate_pct
      FROM v_search_term_report
    """).fetchall()
    c.close()
    sys.stdout.write(json.dumps({"rows":[{
        "term":r[0],"seen":r[1],"avg_fit":r[2],"applied":r[3],
        "skipped":r[4],"apply_rate":r[5]
    } for r in rows]}))
if __name__ == "__main__": main()
