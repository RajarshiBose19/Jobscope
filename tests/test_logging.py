import json
import logging
from jobscope.utils.logging import get_logger, configure_logging

def test_logger_emits_jsonl(tmp_path):
    log_file = tmp_path / "test.log"
    configure_logging(log_file)
    log = get_logger("test.module")
    log.info("hello", extra={"job_id": "abc", "msg_kind": "test_event"})
    for h in logging.getLogger().handlers:
        h.flush()
    line = log_file.read_text().strip().splitlines()[0]
    parsed = json.loads(line)
    assert parsed["level"] == "INFO"
    assert parsed["module"] == "test.module"
    assert parsed["job_id"] == "abc"
    assert parsed["msg_kind"] == "test_event"
    assert "ts" in parsed
