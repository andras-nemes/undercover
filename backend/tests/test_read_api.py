import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.db import DATA, init_db
from backend.main import app

ROOT = Path(__file__).resolve().parents[2]


def count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608


def test_seed(client, tmp_path):
    db_path = tmp_path / "test.db"
    assert count(db_path, "claims") == 25
    assert count(db_path, "policies") == 50
    assert count(db_path, "customers") == 49
    assert count(db_path, "handlers") == 3
    assert count(db_path, "plans") == 3
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT DISTINCT status FROM claims").fetchall() == [
            ("waiting",)
        ]
        assert db.execute("SELECT value FROM settings").fetchone() == (1000.0,)


def test_second_start_does_not_duplicate(client, tmp_path):
    init_db()
    assert count(tmp_path / "test.db", "claims") == 25


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert set(claims[0]) == {
        "claim_id",
        "claim_type",
        "summary",
        "customer_name",
        "amount_claimed",
        "status",
        "decision",
        "payout",
    }
    assert {claim["status"] for claim in claims} == {"waiting"}
    assert claims[0]["customer_name"] == "Maya Patel"


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["policy"]["limits"]["trip_delay_waiting_hours"] == 6
    assert claim["customer"]["name"] == "Maya Patel"
    assert claim["customer"]["previous_claims"][0]["claim_id"] == "CLM-0412"
    assert claim["decision"] is None
    assert claim["payment"] is None
    assert claim["sign_off"] is None
    text = str(claim)
    for private in ("Wayne Street", "555 0143", "1988-03-14", "@example.com"):
        assert private not in text


def test_get_claim_not_found(client):
    assert client.get("/api/claims/CLM-9999").status_code == 404


def test_policy_wording_and_instructions(client):
    wording = client.get("/api/policy-wording")
    assert wording.text == (DATA / "policy_wording.md").read_text(encoding="utf-8")
    instructions = client.get("/api/instructions")
    assert instructions.text == (ROOT / "backend/instructions.md").read_text(
        encoding="utf-8"
    )


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["handler_id"] for h in handlers] == ["HND-01", "HND-02", "HND-03"]
    assert all(h["can_approve_over_limit"] is True for h in handlers)


def test_every_operation_is_documented_and_has_no_optional_inputs():
    schema = TestClient(app).get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            where = f"{method} {path}"
            assert operation.get("operationId"), where
            assert "\n" not in operation["description"].strip(), where
            assert operation["description"].strip(), where
            for parameter in operation.get("parameters", []):
                assert parameter["required"], where
            body = operation.get("requestBody")
            if body:
                ref = body["content"]["application/json"]["schema"]["$ref"]
                model = schema["components"]["schemas"][ref.split("/")[-1]]
                assert set(model["properties"]) == set(model["required"]), where


def test_sources_never_mention_the_answer_key():
    needle = "evals"
    for folder in ("backend", "agent"):
        for source in (ROOT / folder).rglob("*.py"):
            if "tests" not in source.parts:
                assert needle not in source.read_text(encoding="utf-8"), source
    assert needle not in (ROOT / "backend/instructions.md").read_text(encoding="utf-8")
