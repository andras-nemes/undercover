import pytest

pytest_plugins = ["backend.tests.fixtures", "agent.tests.fixtures"]


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch):
    """Keep tests from sending traces to LangSmith.

    A stub model can hold an infinite iterator of replies (see
    test_an_agent_that_never_stops_fails_at_its_call_limit). LangSmith's
    tracer tries to serialize the model's state for a trace payload and,
    for an infinite iterator, never returns: it allocates memory until the
    machine runs out. Tests should never call out to LangSmith regardless.
    """
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
