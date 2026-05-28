from __future__ import annotations
import json, os, sys
from pathlib import Path

WS = Path(os.environ.get("JET_WORKSPACE", ".")).resolve()
SNAP = WS / "projects" / "jobscope" / "state" / "skill_gaps.json"

def main():
    out = {"rows": []}
    if SNAP.exists():
        try:
            data = json.loads(SNAP.read_text(encoding="utf-8"))
            out["rows"] = data.get("rows", [])
        except Exception:
            pass
    sys.stdout.write(json.dumps(out))

if __name__ == "__main__":
    main()
