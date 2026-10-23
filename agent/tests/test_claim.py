import pytest
from langchain_core.messages import AIMessage

from agent import main
from agent.tests.stubs import (
    BrokenModel,
    approve_and_pay,
    call,
    decide,
    script,
)

pytestmark = pytest.mark.usefixtures("use_backend")


def run(llm, claim_id="CLM-1001"):
    return main.run(claim_id, "thread-1", llm)


def test_approve_and_pay(use_backend):
    reply = run(
        script(
            call("get_claim"),
            call("list_sections", document="wording"),
            call("read_section", document="manual", section=9),
            *approve_and_pay(420.0),
        )
    )
    assert reply == "Approved and paid."
    claim = use_backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["reason"] == "Covered by the wording."
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert claim["payment"]["amount"] == 420.0
    assert claim["reads"][0]["title"] == "Repeat claims"


def test_a_section_read_returns_only_that_section(use_backend):
    run(
        script(
            call("read_section", document="wording", section=3),
            AIMessage(content="Read."),
        )
    )
    events = use_backend.get("/api/claims/CLM-1001/events").json()
    result = next(e for e in events if e["kind"] == "tool_result")
    assert result["text"].startswith("## 3. Trip Delay")
    assert "## 4." not in result["text"]


def test_payment_over_the_limit_comes_back_to_the_model_as_an_error(use_backend):
    run(
        script(
            decide("approve", 1250.0),
            call("pay_claim", amount=1250.0),
            AIMessage(content="Waiting for sign-off."),
        )
    )
    claim = use_backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    events = use_backend.get("/api/claims/CLM-1001/events").json()
    assert events[-2]["kind"] == "tool_result"
    assert "needs a sign-off" in events[-2]["text"]


def test_steps_are_logged_in_order(use_backend):
    run(script(call("get_claim"), decide("refer", 0), AIMessage(content="Referred.")))
    events = use_backend.get("/api/claims/CLM-1001/events").json()
    assert [e["kind"] for e in events] == [
        "started",
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "finished",
    ]
    assert events[1]["text"].startswith("get_claim")
    assert events[-1]["text"] == "Referred."


def test_the_agent_works_only_its_own_claim(use_backend):
    run(script(decide("decline", 0), AIMessage(content="Declined.")), "CLM-1002")
    assert use_backend.get("/api/claims/CLM-1002").json()["decision"] is not None
    assert use_backend.get("/api/claims/CLM-1001").json()["decision"] is None


def test_system_prompt_is_the_backends_instructions(use_backend, monkeypatch):
    seen = {}
    create = main.harness.create

    def spy(*args, **kwargs):
        seen["instructions"] = args[1].instructions
        return create(*args, **kwargs)

    monkeypatch.setattr(main.harness, "create", spy)
    run(script(AIMessage(content="Done.")))
    assert seen["instructions"] == use_backend.get("/api/instructions/claim").text


def test_a_failing_model_stops_the_run_with_the_error(use_backend, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="model unavailable"):
        run(BrokenModel(messages=iter([])))
