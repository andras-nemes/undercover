"""The SQLite database and its seed data."""

import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_DB = ROOT / "backend" / "undercover.db"

SCHEMA = """
CREATE TABLE settings (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE plans (plan TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY, name TEXT NOT NULL, previous_claims TEXT NOT NULL
);
CREATE TABLE handlers (
    handler_id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    can_approve_over_limit INTEGER NOT NULL
);
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, customer_id TEXT NOT NULL,
    claim_type TEXT NOT NULL, summary TEXT NOT NULL, story TEXT NOT NULL,
    submitted_on TEXT NOT NULL, incident_date TEXT NOT NULL,
    incident_location TEXT NOT NULL, amount_claimed REAL NOT NULL,
    items TEXT NOT NULL, documents TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
    failures INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE decisions (
    claim_id TEXT PRIMARY KEY, decision TEXT NOT NULL, payout REAL NOT NULL,
    reason TEXT NOT NULL, policy_section TEXT NOT NULL
);
CREATE TABLE payments (
    claim_id TEXT PRIMARY KEY, amount REAL NOT NULL, paid_at TEXT NOT NULL
);
CREATE TABLE sign_offs (
    claim_id TEXT PRIMARY KEY, handler_id TEXT NOT NULL, signed_at TEXT NOT NULL
);
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
    claim_limit INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'running',
    summary TEXT NOT NULL DEFAULT ''
);
CREATE TABLE run_claims (
    run_id INTEGER NOT NULL, claim_id TEXT NOT NULL, PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE todos (
    run_id INTEGER NOT NULL, position INTEGER NOT NULL, content TEXT NOT NULL,
    status TEXT NOT NULL, PRIMARY KEY (run_id, position)
);
CREATE TABLE reads (
    claim_id TEXT NOT NULL, document TEXT NOT NULL, section INTEGER NOT NULL,
    title TEXT NOT NULL, PRIMARY KEY (claim_id, document, section)
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT NOT NULL,
    kind TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def load(name: str) -> Any:
    """Read one JSON file from the data folder."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def connect() -> sqlite3.Connection:
    """Open the database named by UNDERCOVER_DB, or the default one."""
    db = sqlite3.connect(database_path(), check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def get_db() -> Iterator[sqlite3.Connection]:
    """Give a request its own connection."""
    db = connect()
    try:
        yield db
    finally:
        db.close()


def database_path() -> Path:
    """The file the database lives in."""
    return Path(os.getenv("UNDERCOVER_DB", DEFAULT_DB))


def reset_db() -> None:
    """Delete the database. The next start creates it again and seeds it."""
    database_path().unlink(missing_ok=True)


def init_db() -> None:
    """Create the tables and seed them from data/ if the database is new."""
    db = connect()
    with db:
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'claims'"
        ).fetchone():
            db.executescript(SCHEMA)
            seed(db)
    db.close()


def seed(db: sqlite3.Connection) -> None:
    """Load the insurer's records. Customers keep only a name and a claim history."""
    company = load("company.json")
    db.execute(
        "INSERT INTO settings VALUES ('payout_approval_limit', ?)",
        (company["payout_approval_limit"],),
    )
    db.executemany(
        "INSERT INTO plans VALUES (?, ?)",
        [(p["plan"], json.dumps(p)) for p in load("plans.json")["plans"]],
    )
    db.executemany(
        "INSERT INTO policies VALUES (?, ?)",
        [(p["policy_id"], json.dumps(p)) for p in load("policies.json")],
    )
    db.executemany(
        "INSERT INTO customers VALUES (?, ?, ?)",
        [
            (c["customer_id"], c["name"], json.dumps(c["previous_claims"]))
            for c in load("customers.json")
        ],
    )
    db.executemany(
        "INSERT INTO handlers VALUES (?, ?, ?, ?)",
        [
            (h["handler_id"], h["name"], h["role"], int(h["can_approve_over_limit"]))
            for h in load("handlers.json")
        ],
    )
    db.executemany(
        "INSERT INTO claims (claim_id, policy_id, customer_id, claim_type, summary,"
        " story, submitted_on, incident_date, incident_location, amount_claimed,"
        " items, documents) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                c["claim_id"],
                c["policy_id"],
                c["customer_id"],
                c["claim_type"],
                c["summary"],
                c["story"],
                c["submitted_on"],
                c["incident_date"],
                c["incident_location"],
                c["amount_claimed"],
                json.dumps(c["items"]),
                json.dumps(c["documents"]),
            )
            for c in load("claims.json")
        ],
    )


if __name__ == "__main__":
    reset_db()
