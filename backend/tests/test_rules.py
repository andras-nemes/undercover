import sqlite3
from datetime import datetime


def decide(client, claim_id, decision="approve", payout=420.0):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "Covered by the wording.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(client, claim_id, amount):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign_off(client, claim_id, handler_id="HND-01"):
    return client.post(
        f"/api/claims/{claim_id}/sign-off", json={"handler_id": handler_id}
    )


def claim(client, claim_id):
    return client.get(f"/api/claims/{claim_id}").json()


def test_approve_and_pay_under_the_limit(client):
    assert decide(client, "CLM-1001").status_code == 200
    assert claim(client, "CLM-1001")["status"] == "waiting"
    assert pay(client, "CLM-1001", 420.0).status_code == 200
    detail = claim(client, "CLM-1001")
    assert detail["status"] == "decided"
    assert detail["decision"]["payout"] == 420.0
    assert detail["payment"]["amount"] == 420.0


def test_payment_over_the_limit_is_blocked_until_sign_off(client):
    decide(client, "CLM-1001", payout=1250.0)
    assert claim(client, "CLM-1001")["status"] == "awaiting_sign_off"
    assert pay(client, "CLM-1001", 1250.0).status_code == 409
    detail = claim(client, "CLM-1001")
    assert detail["status"] == "awaiting_sign_off"
    assert detail["payment"] is None


def test_the_limit_is_strict(client):
    decide(client, "CLM-1001", payout=1000.0)
    assert pay(client, "CLM-1001", 1000.0).status_code == 200
    decide(client, "CLM-1002", payout=1000.01)
    assert claim(client, "CLM-1002")["status"] == "awaiting_sign_off"
    assert pay(client, "CLM-1002", 1000.01).status_code == 409


def test_sign_off_releases_the_payment(client):
    decide(client, "CLM-1001", payout=1250.0)
    response = sign_off(client, "CLM-1001", "HND-02")
    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == "decided"
    assert detail["sign_off"]["handler_name"] == "Marcus Oyelaran"
    assert detail["payment"]["amount"] == 1250.0
    assert sign_off(client, "CLM-1001").status_code == 409
    assert pay(client, "CLM-1001", 1250.0).status_code == 409


def test_sign_off_needs_the_right_state_and_handler(client):
    assert sign_off(client, "CLM-1001").status_code == 409
    decide(client, "CLM-1001", payout=1250.0)
    assert sign_off(client, "CLM-1001", "HND-99").status_code == 404
    assert sign_off(client, "CLM-9999").status_code == 404


def test_a_handler_who_cannot_approve_cannot_sign_off(client, tmp_path):
    decide(client, "CLM-1001", payout=1250.0)
    with sqlite3.connect(tmp_path / "test.db") as db:
        db.execute(
            "UPDATE handlers SET can_approve_over_limit = 0 WHERE handler_id = 'HND-03'"
        )
    assert sign_off(client, "CLM-1001", "HND-03").status_code == 403


def test_only_an_approval_can_be_paid_for_its_amount(client):
    assert pay(client, "CLM-1001", 10.0).status_code == 409
    decide(client, "CLM-1001", "decline", 0)
    assert pay(client, "CLM-1001", 10.0).status_code == 409
    decide(client, "CLM-1002", "refer", 0)
    assert pay(client, "CLM-1002", 10.0).status_code == 409
    decide(client, "CLM-1003", payout=100.0)
    assert pay(client, "CLM-1003", 99.0).status_code == 409
    assert pay(client, "CLM-1003", 100.0).status_code == 200
    assert pay(client, "CLM-1003", 100.0).status_code == 409
    assert pay(client, "CLM-9999", 100.0).status_code == 404


def test_one_decision_per_claim(client):
    assert decide(client, "CLM-1001").status_code == 200
    assert decide(client, "CLM-1001").status_code == 409
    assert decide(client, "CLM-9999").status_code == 404


def test_payout_must_match_the_decision(client):
    assert decide(client, "CLM-1001", "approve", 0).status_code == 422
    assert decide(client, "CLM-1001", "decline", 50).status_code == 422
    assert decide(client, "CLM-1001", "refer", 50).status_code == 422
    assert claim(client, "CLM-1001")["decision"] is None


def test_decline_and_refer_are_decided_at_once(client):
    decide(client, "CLM-1001", "decline", 0)
    decide(client, "CLM-1002", "refer", 0)
    assert claim(client, "CLM-1001")["status"] == "decided"
    assert claim(client, "CLM-1002")["status"] == "decided"
    summaries = {c["claim_id"]: c for c in client.get("/api/claims").json()}
    assert summaries["CLM-1001"]["decision"] == "decline"
    assert summaries["CLM-1002"]["payout"] == 0


def test_events_come_back_in_order(client):
    for text in ("one", "two", "three"):
        response = client.post(
            "/api/claims/CLM-1001/events", json={"kind": "note", "text": text}
        )
        assert response.status_code == 200
    events = client.get("/api/claims/CLM-1001/events").json()
    assert [e["text"] for e in events] == ["one", "two", "three"]
    assert all(e["kind"] == "note" for e in events)
    datetime.fromisoformat(events[0]["created_at"])
    assert client.get("/api/claims/CLM-1002/events").json() == []
    assert client.get("/api/claims/CLM-9999/events").status_code == 404
    post = client.post("/api/claims/CLM-9999/events", json={"kind": "n", "text": "t"})
    assert post.status_code == 404
