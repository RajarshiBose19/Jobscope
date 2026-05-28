import secrets
import uuid
from datetime import datetime, timezone

def new_uuid() -> str:
    return str(uuid.uuid4())

def new_session_id() -> str:
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return f"{ts}-{secrets.token_hex(2)}"
