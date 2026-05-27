"""Emit Plotly traces for the salary-by-search-term box plot (type='chart')."""
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
          SELECT search_term, salary_min_lpa, salary_max_lpa
          FROM jobs
          WHERE salary_min_lpa IS NOT NULL OR salary_max_lpa IS NOT NULL
        """).fetchall()
        c.close()
    by_term = {}
    for term, smin, smax in rows:
        bucket = by_term.setdefault(term, [])
        if smin is not None: bucket.append(smin)
        if smax is not None: bucket.append(smax)
    traces = [
        {"type": "box", "orientation": "h", "name": term, "x": vals}
        for term, vals in by_term.items()
    ]
    sys.stdout.write(json.dumps({
        "traces": traces,
        "plotlyLayout": {
            "paper_bgcolor": "#0e1116", "plot_bgcolor": "#0e1116",
            "font": {"color": "#e6edf3"},
            "margin": {"l": 160, "r": 20, "t": 30, "b": 40},
            "xaxis": {"title": "LPA"},
            "showlegend": False,
            "shapes": [{"type": "line", "x0": 12, "x1": 12, "yref": "paper",
                        "y0": 0, "y1": 1, "line": {"color": "#f1c40f", "dash": "dash"}}],
            "annotations": [{"x": 12, "yref": "paper", "y": 1.04,
                             "text": "expected 12 LPA", "showarrow": False,
                             "font": {"color": "#f1c40f", "size": 11}}],
        },
    }))

if __name__ == "__main__":
    main()
