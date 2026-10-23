from pathlib import Path

import pytest

from agent import api

AGENT = Path(api.__file__).parent


def test_calls_return_the_backends_replies(use_backend):
    assert "CLM-1001" in api.get_claim("CLM-1001")
    assert "Trip Delay" in api.list_sections("wording")
    assert api.read_section("CLM-1001", "manual", 9).startswith("## 9. Repeat claims")
    assert "UnderCover Agent" in api.get_instructions("claim")


def test_a_refusal_raises_with_the_backends_reason(use_backend):
    with pytest.raises(api.ApiError, match="Error 404: Claim CLM-9999 not found"):
        api.get_claim("CLM-9999")


def test_backend_client_uses_backend_url(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://example.test:9")
    with api.backend() as http:
        assert str(http.base_url) == "http://example.test:9"


def test_only_the_api_module_talks_to_the_backend():
    for source in AGENT.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "import backend" not in text
        assert "from backend" not in text
        assert "data/" not in text
        if source.name != "api.py":
            assert '"/api/' not in text, source.name
            assert "httpx" not in text, source.name
