from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(os.environ.get("JET_WORKSPACE", ".")).resolve()
SNAPSHOT = WORKSPACE / "projects" / "jobscope" / "state" / "current_job.json"

def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def _staleness(updated_at_iso: str) -> str:
    try:
        u = datetime.fromisoformat(updated_at_iso.replace("Z", "+00:00"))
        secs = (datetime.now(timezone.utc) - u).total_seconds()
    except Exception:
        return "unknown"
    if secs < 10:   return "live"
    if secs < 60:   return "slow"
    return "stalled"

def main() -> None:
    if not SNAPSHOT.exists():
        payload = {"state": "missing", "_meta": {"computed_at": _iso()}}
    else:
        try:
            payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        except Exception as e:
            payload = {"state": "error", "error": {"kind": "snapshot_parse", "message": str(e)}}
    payload["_meta"] = {
        "computed_at": _iso(),
        "staleness": _staleness(payload.get("last_updated_at", "")),
    }
    sys.stdout.write(json.dumps(payload, default=str))

if __name__ == "__main__":
    main()
