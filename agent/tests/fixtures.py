from contextlib import nullcontext

import pytest

from agent import api


@pytest.fixture
def use_backend(monkeypatch, client):
    """Route the agent's calls to the test backend, on a fresh database."""
    monkeypatch.setattr(api, "backend", lambda: nullcontext(client))
    return client
