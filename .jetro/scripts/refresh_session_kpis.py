from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path(os.environ.get("JET_WORKSPACE", ".")).resolve()
SNAP = WS / "projects" / "jobscope" / "state" / "session_kpis.json"

def main():
    out = {"_meta": {"computed_at": datetime.now(timezone.utc).isoformat()}}
    if SNAP.exists():
        try:
            out.update(json.loads(SNAP.read_text(encoding="utf-8")))
        except Exception:
            pass
    out.setdefault("evaluated", 0)
    out.setdefault("applied", 0)
    out.setdefault("skipped", 0)
    out.setdefault("bookmarked", 0)
    out.setdefault("avg_fit", None)
    sys.stdout.write(json.dumps(out))

if __name__ == "__main__":
    main()
