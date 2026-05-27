"""Emit Plotly traces for the skill-gaps bar chart (type='chart')."""
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
          SELECT display_name, jobs_where_missing
          FROM v_skill_gaps
          WHERE jobs_where_missing > 0
          ORDER BY jobs_where_missing DESC LIMIT 25
        """).fetchall()
        c.close()
    skills = [r[0] for r in rows][::-1]
    miss   = [r[1] for r in rows][::-1]
    sys.stdout.write(json.dumps({
        "traces": [{
            "type": "bar", "orientation": "h",
            "x": miss, "y": skills,
            "marker": {"color": "#e74c3c"},
            "hovertemplate": "%{y}: missing in %{x} jobs<extra></extra>",
        }],
        "plotlyLayout": {
            "paper_bgcolor": "#0e1116", "plot_bgcolor": "#0e1116",
            "font": {"color": "#e6edf3"},
            "margin": {"l": 140, "r": 20, "t": 20, "b": 30},
            "xaxis": {"title": "Jobs where missing"},
            "yaxis": {"automargin": True},
            "showlegend": False,
        },
    }))

if __name__ == "__main__":
    main()
