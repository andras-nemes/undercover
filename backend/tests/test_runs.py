import pytest


def new_run(client, limit=0):
    return client.post("/api/runs", json={"limit": limit}).json()


def start(client, run_id, claim_id):
    return client.post(f"/api/runs/{run_id}/claims/{claim_id}/start")


def release(client, claim_id, reason="model unavailable"):
    return client.post(f"/api/claims/{claim_id}/release", json={"reason": reason})


def status(client, claim_id):
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def decide(client, claim_id, decision, payout):
    body = {
        "decision": decision,
        "payout": payout,
        "reason": "Covered.",
        "policy_section": "Section 3",
    }
    return client.post(f"/api/claims/{claim_id}/decision", json=body)


def queue_ids(client, run_id):
    return [c["claim_id"] for c in client.get(f"/api/runs/{run_id}/queue").json()]


@pytest.fixture
def running(client, monkeypatch):
    """Starts runs whose agent does nothing, so the run stays running."""
    monkeypatch.setattr("backend.runner.work_run", lambda run_id: None)

    def make(limit=0):
        return new_run(client, limit)["run_id"]

    return make


def test_no_run_yet(client):
    assert client.get("/api/runs/latest").json() is None


def test_start_run(client, running):
    run_id = running(5)
    run = client.get("/api/runs/latest").json()
    assert run["run_id"] == run_id
    assert run["limit"] == 5
    assert run["status"] == "running"
    assert run["todos"] == []
    assert client.post("/api/runs", json={"limit": -1}).status_code == 422


def test_a_second_run_is_refused_while_one_is_running(client, running):
    running(5)
    assert client.post("/api/runs", json={"limit": 5}).status_code == 409


def test_todos_are_stored_and_replaced(client, running):
    run_id = running()
    todos = [
        {"content": "CLM-1001", "status": "done"},
        {"content": "CLM-1002", "status": "in_progress"},
        {"content": "CLM-1003", "status": "todo"},
        {"content": "CLM-1004", "status": "left_for_handler"},
    ]
    client.put(f"/api/runs/{run_id}/todos", json={"todos": todos})
    assert client.get("/api/runs/latest").json()["todos"] == todos
    client.put(f"/api/runs/{run_id}/todos", json={"todos": todos[:1]})
    assert client.get("/api/runs/latest").json()["todos"] == todos[:1]
    bad = [{"content": "x", "status": "maybe"}]
    response = client.put(f"/api/runs/{run_id}/todos", json={"todos": bad})
    assert response.status_code == 422
    assert client.put("/api/runs/99/todos", json={"todos": []}).status_code == 404


def test_the_cap_leaves_the_rest_waiting(client, running):
    run_id = running(2)
    assert len(queue_ids(client, run_id)) == 25
    assert start(client, run_id, "CLM-1001").status_code == 200
    assert start(client, run_id, "CLM-1002").status_code == 200
    assert start(client, run_id, "CLM-1003").status_code == 409
    assert queue_ids(client, run_id) == []
    waiting = [c for c in client.get("/api/claims").json() if c["status"] == "waiting"]
    assert len(waiting) == 23


def test_no_cap_takes_every_claim(client, running):
    run_id = running(0)
    for number in range(1001, 1011):
        assert start(client, run_id, f"CLM-{number}").status_code == 200


def test_a_claim_that_is_not_waiting_cannot_be_started(client, running):
    run_id = running()
    start(client, run_id, "CLM-1001")
    assert start(client, run_id, "CLM-1001").status_code == 409
    assert start(client, run_id, "CLM-9999").status_code == 404


def test_a_failed_claim_does_not_stop_the_run(client, running):
    run_id = running()
    start(client, run_id, "CLM-1001")
    release(client, "CLM-1001")
    assert start(client, run_id, "CLM-1002").status_code == 200


def test_a_failed_claim_goes_back_in_the_queue_without_using_the_cap(client, running):
    run_id = running(1)
    start(client, run_id, "CLM-1001")
    response = release(client, "CLM-1001")
    assert response.json()["status"] == "waiting"
    assert status(client, "CLM-1001") == "waiting"
    events = client.get("/api/claims/CLM-1001/events").json()
    assert events[0]["kind"] == "error"
    assert "Attempt 1 failed: model unavailable" in events[0]["text"]
    assert queue_ids(client, run_id) == ["CLM-1001"]
    assert start(client, run_id, "CLM-1001").status_code == 200
    assert start(client, run_id, "CLM-1002").status_code == 409


def test_a_claim_that_fails_twice_is_left_for_a_handler(client, running):
    run_id = running()
    for _ in range(2):
        start(client, run_id, "CLM-1001")
        release(client, "CLM-1001")
    assert status(client, "CLM-1001") == "needs_handler"
    assert "CLM-1001" not in queue_ids(client, run_id)
    assert start(client, run_id, "CLM-1001").status_code == 409
    events = client.get("/api/claims/CLM-1001/events").json()
    assert "Left for a handler" in events[-1]["text"]


def test_nothing_is_decided_or_paid_twice_after_a_failure(client, running):
    run_id = running()
    start(client, run_id, "CLM-1001")
    assert decide(client, "CLM-1001", "approve", 420.0).status_code == 200
    release(client, "CLM-1001")
    assert status(client, "CLM-1001") == "waiting"
    start(client, run_id, "CLM-1001")
    assert decide(client, "CLM-1001", "approve", 420.0).status_code == 409
    pay = {"amount": 420.0}
    assert client.post("/api/claims/CLM-1001/payment", json=pay).status_code == 200
    assert client.post("/api/claims/CLM-1001/payment", json=pay).status_code == 409


def test_release_changes_nothing_on_a_claim_that_is_settled(client, running):
    run_id = running()
    start(client, run_id, "CLM-1001")
    decide(client, "CLM-1001", "decline", 0)
    assert release(client, "CLM-1001").json()["status"] == "decided"
    start(client, run_id, "CLM-1002")
    decide(client, "CLM-1002", "approve", 1250.0)
    assert release(client, "CLM-1002").json()["status"] == "awaiting_sign_off"
    assert client.get("/api/claims/CLM-1002/events").json() == []
    assert release(client, "CLM-9999").status_code == 404


def test_finish_refuses_to_miss_claims_then_stores_the_summary(client, running):
    run_id = running(2)
    finish = {"summary": "Two claims."}
    refused = client.post(f"/api/runs/{run_id}/finish", json=finish)
    assert refused.status_code == 409
    assert "CLM-1001" in refused.json()["detail"]
    for claim_id in ("CLM-1001", "CLM-1002"):
        start(client, run_id, claim_id)
        decide(client, claim_id, "decline", 0)
    done = client.post(f"/api/runs/{run_id}/finish", json=finish)
    assert done.status_code == 200
    assert done.json()["status"] == "finished"
    assert client.get("/api/runs/latest").json()["summary"] == "Two claims."
    assert status(client, "CLM-1003") == "waiting"
    assert client.post(f"/api/runs/{run_id}/finish", json=finish).status_code == 409


def test_finish_refuses_a_claim_waiting_for_its_retry(client, running):
    run_id = running(1)
    start(client, run_id, "CLM-1001")
    release(client, "CLM-1001")
    refused = client.post(f"/api/runs/{run_id}/finish", json={"summary": "x"})
    assert refused.status_code == 409
    assert refused.json()["detail"] == "Claims still to work: CLM-1001"


def test_a_finished_run_cannot_be_changed(client, running):
    run_id = running(1)
    start(client, run_id, "CLM-1001")
    decide(client, "CLM-1001", "decline", 0)
    client.post(f"/api/runs/{run_id}/finish", json={"summary": "Done."})
    todos = {"todos": []}
    assert client.put(f"/api/runs/{run_id}/todos", json=todos).status_code == 409
    assert start(client, run_id, "CLM-1002").status_code == 409
