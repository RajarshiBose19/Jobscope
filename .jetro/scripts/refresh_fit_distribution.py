"""Emit Plotly traces for the fit-score distribution histogram (type='chart')."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "Lib", "site-packages"))
import duckdb

DB = Path(os.environ.get("JET_WORKSPACE", ".")).resolve() / "projects/jobscope/jobscope.duckdb"

def main():
    scores = []
    if DB.exists():
        c = duckdb.connect(str(DB), read_only=True)
        scores = [r[0] for r in c.execute(
            "SELECT fit_score FROM v_job_analysis WHERE fit_score IS NOT NULL"
        ).fetchall()]
        c.close()
    sys.stdout.write(json.dumps({
        "traces": [{
            "type": "histogram", "x": scores,
            "xbins": {"start": 0, "end": 100, "size": 10},
            "marker": {"color": "#5dade2"},
        }],
        "plotlyLayout": {
            "paper_bgcolor": "#0e1116", "plot_bgcolor": "#0e1116",
            "font": {"color": "#e6edf3"},
            "margin": {"l": 40, "r": 20, "t": 20, "b": 40}, "bargap": 0.05,
            "xaxis": {"title": "Fit score", "range": [0, 100]},
            "yaxis": {"title": "Jobs"},
            "showlegend": False,
        },
    }))

if __name__ == "__main__":
    main()
