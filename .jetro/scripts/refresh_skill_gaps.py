import json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Lib", "site-packages"))
import duckdb
DB = Path(os.environ.get("JET_WORKSPACE",".")).resolve() / "projects/jobscope/jobscope.duckdb"
def main():
    if not DB.exists(): sys.stdout.write(json.dumps({"rows":[]})); return
    c = duckdb.connect(str(DB), read_only=True)
    rows = c.execute("""
      SELECT display_name, jobs_asking, jobs_where_missing
      FROM v_skill_gaps
      WHERE jobs_where_missing > 0
      ORDER BY jobs_where_missing DESC LIMIT 25
    """).fetchall()
    c.close()
    sys.stdout.write(json.dumps({"rows":[
        {"skill":r[0],"asking":r[1],"missing":r[2]} for r in rows]}))
if __name__ == "__main__": main()
