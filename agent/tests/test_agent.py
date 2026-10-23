from contextlib import nullcontext
from pathlib import Path

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name, **args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": f"{name}-1"}]
    )


def decide(claim_id, decision, payout):
    return call(
        "decide_claim",
        claim_id=claim_id,
        decision=decision,
        payout=payout,
        reason="Covered by the wording.",
        policy_section="Section 3, Trip Delay",
    )


def script(*replies):
    return StubModel(messages=iter(replies))


def use(monkeypatch, client):
    monkeypatch.setattr(main, "backend", lambda: nullcontext(client))


def test_tools_return_backend_replies_and_errors(monkeypatch, client):
    use(monkeypatch, client)
    assert "CLM-1001" in main.get_claim.invoke({"claim_id": "CLM-1001"})
    sections = main.list_sections.invoke({"document": "wording"})
    assert "Trip Delay" in sections
    read = {"claim_id": "CLM-1001", "document": "manual", "section": 9}
    assert main.read_section.invoke(read).startswith("## 9. Repeat claims")
    missing = main.get_claim.invoke({"claim_id": "CLM-9999"})
    assert missing == "Error 404: Claim CLM-9999 not found"


def test_approve_and_pay(monkeypatch, client):
    use(monkeypatch, client)
    reply = main.run(
        "CLM-1001",
        "thread-1",
        script(
            call("get_claim", claim_id="CLM-1001"),
            call("list_sections", document="wording"),
            call("read_section", claim_id="CLM-1001", document="manual", section=9),
            decide("CLM-1001", "approve", 420.0),
            call("pay_claim", claim_id="CLM-1001", amount=420.0),
            AIMessage(content="Approved and paid."),
        ),
    )
    assert reply == "Approved and paid."
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["reason"] == "Covered by the wording."
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert claim["payment"]["amount"] == 420.0
    assert claim["reads"][0]["title"] == "Repeat claims"


def test_payment_over_the_limit_comes_back_as_an_error(monkeypatch, client):
    use(monkeypatch, client)
    main.run(
        "CLM-1001",
        "thread-1",
        script(
            decide("CLM-1001", "approve", 1250.0),
            call("pay_claim", claim_id="CLM-1001", amount=1250.0),
            AIMessage(content="Waiting for sign-off."),
        ),
    )
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    events = client.get("/api/claims/CLM-1001/events").json()
    assert "needs a sign-off" in events[-2]["text"]


def test_steps_are_logged_in_order(monkeypatch, client):
    use(monkeypatch, client)
    main.run(
        "CLM-1001",
        "thread-1",
        script(
            call("get_claim", claim_id="CLM-1001"),
            decide("CLM-1001", "refer", 0),
            AIMessage(content="Referred."),
        ),
    )
    events = client.get("/api/claims/CLM-1001/events").json()
    assert [e["kind"] for e in events] == [
        "started",
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "finished",
    ]
    assert events[1]["text"].startswith("get_claim")
    assert len(events[2]["text"]) <= main.RESULT_LIMIT
    assert events[-1]["text"] == "Referred."


def test_system_prompt_is_the_backends_instructions(monkeypatch, client):
    use(monkeypatch, client)
    seen = {}
    create_agent = main.create_agent

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return create_agent(*args, **kwargs)

    monkeypatch.setattr(main, "create_agent", spy)
    main.run("CLM-1001", "thread-1", script(AIMessage(content="Done.")))
    assert seen["system_prompt"] == client.get("/api/instructions/claim").text


def test_agent_reaches_the_data_only_through_the_api():
    text = Path(main.__file__).read_text(encoding="utf-8")
    assert "import backend" not in text
    assert "from backend" not in text
    assert "data/" not in text


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_backend_client_uses_backend_url(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://example.test:9")
    with main.backend() as http:
        assert str(http.base_url) == "http://example.test:9"
