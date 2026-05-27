import json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Lib", "site-packages"))
import duckdb
DB = Path(os.environ.get("JET_WORKSPACE",".")).resolve() / "projects/jobscope/jobscope.duckdb"
def main():
    if not DB.exists(): sys.stdout.write(json.dumps({"scores":[]})); return
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute("SELECT fit_score FROM v_job_analysis WHERE fit_score IS NOT NULL").fetchall()
    c.close()
    sys.stdout.write(json.dumps({"scores":[r[0] for r in rows]}))
if __name__ == "__main__": main()
