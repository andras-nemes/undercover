import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.db import init_db, reset_db
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


def test_instructions_for_each_agent(client):
    for agent in ("queue", "claim"):
        text = (ROOT / f"backend/instructions_{agent}.md").read_text(encoding="utf-8")
        assert client.get(f"/api/instructions/{agent}").text == text
    assert client.get("/api/instructions/other").status_code == 404


def test_sections_of_each_document(client):
    wording = client.get("/api/documents/wording/sections").json()
    assert len(wording) == 12
    assert wording[2] == {"number": 3, "title": "Trip Delay"}
    manual = client.get("/api/documents/manual/sections").json()
    assert len(manual) == 14
    assert manual[8] == {"number": 9, "title": "Repeat claims"}
    assert client.get("/api/documents/letters/sections").status_code == 404


def read(client, claim_id, document, section):
    body = {"document": document, "section": section}
    return client.post(f"/api/claims/{claim_id}/reads", json=body)


def test_read_section_returns_only_that_section(client):
    text = read(client, "CLM-1001", "manual", 9).text
    assert text.startswith("## 9. Repeat claims")
    assert "third claim" in text
    assert "## 8." not in text
    assert "## 10." not in text
    assert read(client, "CLM-1001", "wording", 12).text.startswith("## 12.")


def test_read_section_not_found(client):
    assert read(client, "CLM-1001", "manual", 99).status_code == 404
    assert read(client, "CLM-9999", "manual", 9).status_code == 404
    assert read(client, "CLM-1001", "letters", 9).status_code == 422


def test_reads_are_recorded_once_in_order(client):
    read(client, "CLM-1001", "wording", 3)
    read(client, "CLM-1001", "manual", 9)
    read(client, "CLM-1001", "wording", 3)
    reads = client.get("/api/claims/CLM-1001").json()["reads"]
    assert reads == [
        {"document": "wording", "section": 3, "title": "Trip Delay"},
        {"document": "manual", "section": 9, "title": "Repeat claims"},
    ]
    assert client.get("/api/claims/CLM-1002").json()["reads"] == []


def test_reset_removes_the_database(client, tmp_path):
    path = tmp_path / "test.db"
    assert path.exists()
    reset_db()
    assert not path.exists()
    init_db()
    assert count(path, "claims") == 25


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
    for agent in ("queue", "claim"):
        instructions = ROOT / f"backend/instructions_{agent}.md"
        assert needle not in instructions.read_text(encoding="utf-8")
