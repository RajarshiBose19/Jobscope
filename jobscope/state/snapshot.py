from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def idle_payload(session_id: str = "") -> dict[str, Any]:
    return {
        "state": "idle",
        "session_id": session_id,
        "last_updated_at": _now_iso(),
        "scraper_pid": os.getpid(),
    }

def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload.setdefault("last_updated_at", _now_iso())
    payload.setdefault("scraper_pid", os.getpid())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    last_err: Exception | None = None
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as e:
            last_err = e
            time.sleep(0.05 * (attempt + 1))
    if last_err is not None:
        raise last_err

def read_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"state": "idle", "last_updated_at": _now_iso(), "missing": True}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"state": "error", "error": "snapshot_unparseable",
                "last_updated_at": _now_iso()}
