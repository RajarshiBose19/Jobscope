import pytest
from unittest.mock import MagicMock, patch
from jobscope.ai.client import GeminiClient, RateLimitError, AnalysisFailure

def test_rotates_on_429():
    keys = ["k1", "k2", "k3"]
    client = GeminiClient(keys=keys, model="m")
    fake = MagicMock()
    fake.text = '{"ok": true}'
    side = [RateLimitError("429"), fake]
    with patch.object(client, "_call_once", side_effect=side) as call_once:
        out = client.generate_json(system="s", user="u", response_schema=dict)
    assert out.text == '{"ok": true}'
    assert call_once.call_count == 2
    assert client._current_key == "k2"

def test_raises_after_all_keys_429():
    keys = ["k1", "k2"]
    client = GeminiClient(keys=keys, model="m")
    with patch.object(client, "_call_once", side_effect=RateLimitError("429")):
        with pytest.raises(AnalysisFailure) as ei:
            client.generate_json(system="s", user="u", response_schema=dict)
    assert "exhausted" in str(ei.value).lower()
