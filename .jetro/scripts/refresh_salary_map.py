import json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Lib", "site-packages"))
import duckdb
DB = Path(os.environ.get("JET_WORKSPACE",".")).resolve() / "projects/jobscope/jobscope.duckdb"
def main():
    if not DB.exists(): sys.stdout.write(json.dumps({"rows":[]})); return
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute("""
      SELECT search_term, salary_min_lpa, salary_max_lpa
      FROM jobs
      WHERE salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL
    """).fetchall()
    c.close()
    sys.stdout.write(json.dumps({"rows":[
        {"term":r[0],"min":r[1],"max":r[2]} for r in rows]}))
if __name__ == "__main__": main()
