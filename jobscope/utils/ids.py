"""ID generators."""
import secrets
import uuid
from datetime import datetime, timezone

def new_uuid() -> str:
    return str(uuid.uuid4())

def new_session_id() -> str:
    """ISO timestamp + 4-hex suffix. Sortable, readable, unique."""
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return f"{ts}-{secrets.token_hex(2)}"
