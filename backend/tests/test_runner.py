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


def broken(claim_id, thread_id):
    raise RuntimeError("model unavailable")


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
    monkeypatch.setattr(runner, "run_agent", broken)
    client.post("/api/claims/CLM-1001/run")
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    events = client.get("/api/claims/CLM-1001/events").json()
    assert [e["kind"] for e in events] == ["error"]
    assert "model unavailable" in events[0]["text"]
    assert "Back in the queue" in events[0]["text"]


def test_a_claim_that_fails_twice_is_left_for_a_handler(client, monkeypatch):
    monkeypatch.setattr(runner, "run_agent", broken)
    client.post("/api/claims/CLM-1001/run")
    client.post("/api/claims/CLM-1001/run")
    assert client.get("/api/claims/CLM-1001").json()["status"] == "needs_handler"
    assert client.post("/api/claims/CLM-1001/run").status_code == 409


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
    events = client.get("/api/claims/CLM-1001/events").json()
    assert "stopped before it finished" in events[0]["text"]


def test_a_queue_run_that_raises_is_marked_failed(client, monkeypatch):
    def broken_queue(run_id):
        raise RuntimeError("provider down")

    monkeypatch.setattr(runner, "run_queue", broken_queue)
    client.post("/api/runs", json={"limit": 0})
    run = client.get("/api/runs/latest").json()
    assert run["status"] == "failed"
    assert "provider down" in run["summary"]


def test_a_queue_run_that_ends_without_finishing_is_marked_failed(client, monkeypatch):
    monkeypatch.setattr(runner, "run_queue", lambda run_id: "Done.")
    client.post("/api/runs", json={"limit": 0})
    assert client.get("/api/runs/latest").json()["status"] == "failed"


def test_a_queue_run_that_finishes_stays_finished(client, monkeypatch):
    def works_one_claim(run_id):
        client.post(f"/api/runs/{run_id}/claims/CLM-1001/start")
        decision = {
            "decision": "decline",
            "payout": 0,
            "reason": "Not covered.",
            "policy_section": "Section 9",
        }
        client.post("/api/claims/CLM-1001/decision", json=decision)
        client.post(f"/api/runs/{run_id}/finish", json={"summary": "One claim."})

    monkeypatch.setattr(runner, "run_queue", works_one_claim)
    client.post("/api/runs", json={"limit": 1})
    run = client.get("/api/runs/latest").json()
    assert run["status"] == "finished"
    assert run["summary"] == "One claim."
