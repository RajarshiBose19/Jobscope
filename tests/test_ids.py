import re
from jobscope.utils.ids import new_session_id, new_uuid

def test_session_id_format():
    sid = new_session_id()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}-[0-9a-f]{4}$", sid), sid

def test_new_uuid_is_unique():
    a, b = new_uuid(), new_uuid()
    assert a != b
    assert len(a) == 36
