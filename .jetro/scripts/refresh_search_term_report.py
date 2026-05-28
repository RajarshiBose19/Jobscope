from __future__ import annotations
import json, os, sys
from pathlib import Path

WS = Path(os.environ.get("JET_WORKSPACE", ".")).resolve()
SNAP = WS / "projects" / "jobscope" / "state" / "search_term_report.json"

def main():
    out = {"rows": []}
    if SNAP.exists():
        try:
            out = json.loads(SNAP.read_text(encoding="utf-8"))
        except Exception:
            pass
    sys.stdout.write(json.dumps(out))

if __name__ == "__main__":
    main()
