import itertools
import time

import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.messages import AIMessage, HumanMessage

from agent import harness, main
from agent.tests.stubs import StubModel, call


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = harness.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    named = harness.model()
    assert named.model_name == "openrouter/free"
    assert named.reasoning_effort is None


def test_an_agent_that_never_stops_fails_at_its_call_limit(use_backend, monkeypatch):
    monkeypatch.setattr(main, "CLAIM_CALL_LIMIT", 3)
    forever = StubModel(
        messages=itertools.cycle([call("list_sections", document="wording")])
    )
    with pytest.raises(ModelCallLimitExceededError):
        main.run("CLM-1001", "thread-1", forever)


def test_a_failed_model_call_is_tried_again(use_backend, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)

    class Flaky(StubModel):
        failed: bool = False

        def _generate(self, *args, **kwargs):
            if not self.failed:
                self.failed = True
                raise TimeoutError("timed out")
            return super()._generate(*args, **kwargs)

    reply = main.run("CLM-1001", "thread-1", Flaky(messages=iter([AIMessage("Done.")])))
    assert reply == "Done."


def test_steps_describe_each_message():
    assert harness.steps(AIMessage("Done.")) == [("finished", "Done.")]
    assert harness.steps(call("list_queue")) == [("tool_call", "list_queue {}")]
    assert harness.steps(HumanMessage("Claim CLM-1001")) == []
