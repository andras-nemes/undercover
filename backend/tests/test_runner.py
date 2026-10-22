from contextlib import nullcontext

import pytest
from langchain_core.messages import AIMessage

from agent import main
from agent.tests.test_agent import StubModel, call, decide
from backend import runner


@pytest.fixture
def stub_agent(monkeypatch, client):
    """Make the runner's agent a stub that approves $420.00 and pays it."""
    monkeypatch.setattr(main, "backend", lambda: nullcontext(client))

    def run(claim_id, thread_id):
        replies = [
            decide(claim_id, "approve", 420.0),
            call("pay_claim", claim_id=claim_id, amount=420.0),
            AIMessage(content="Paid."),
        ]
        return main.run(claim_id, thread_id, StubModel(messages=iter(replies)))

    monkeypatch.setattr(runner, "run_agent", run)


def test_run_agent_starts_the_claim_and_the_agent_decides(client, stub_agent):
    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 420.0


def test_a_claim_that_is_not_waiting_cannot_be_run(client, stub_agent):
    client.post("/api/claims/CLM-1001/run")
    assert client.post("/api/claims/CLM-1001/run").status_code == 409
    assert client.post("/api/claims/CLM-9999/run").status_code == 404


def test_a_failed_run_returns_the_claim_to_waiting(client, monkeypatch):
    def broken(claim_id, thread_id):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(runner, "run_agent", broken)
    client.post("/api/claims/CLM-1001/run")
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    events = client.get("/api/claims/CLM-1001/events").json()
    assert [e["kind"] for e in events] == ["error"]
    assert "model unavailable" in events[0]["text"]


def test_an_unpaid_approval_goes_back_to_waiting(client, monkeypatch):
    def forgetful(claim_id, thread_id):
        client.post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": "approve",
                "payout": 50.0,
                "reason": "Covered.",
                "policy_section": "Section 3",
            },
        )

    monkeypatch.setattr(runner, "run_agent", forgetful)
    client.post("/api/claims/CLM-1001/run")
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert claim["decision"]["payout"] == 50.0


def test_run_waiting_works_every_waiting_claim_in_turn(client, stub_agent):
    client.post("/api/claims/CLM-1001/run")
    response = client.post("/api/run-waiting")
    assert len(response.json()) == 24
    statuses = {c["status"] for c in client.get("/api/claims").json()}
    assert statuses == {"decided"}


def test_run_waiting_skips_claims_that_are_no_longer_waiting(client, stub_agent):
    client.post("/api/claims/CLM-1001/run")
    runner.work_waiting(["CLM-1001", "CLM-1002"])
    claim = client.get("/api/claims/CLM-1001/events").json()
    assert [e["kind"] for e in claim].count("started") == 1
    assert client.get("/api/claims/CLM-1002").json()["status"] == "decided"
