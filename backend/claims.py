"""Reading claims from the database."""

import json
import sqlite3

from fastapi import HTTPException

from backend.models import (
    ClaimDetail,
    ClaimSummary,
    Customer,
    Decision,
    Handler,
    Payment,
    Plan,
    Policy,
    SignOff,
)


def not_found(what: str, key: str) -> HTTPException:
    """Build the 404 for a missing record."""
    return HTTPException(status_code=404, detail=f"{what} {key} not found")


def list_summaries(db: sqlite3.Connection) -> list[ClaimSummary]:
    """Every claim with its customer's name and, once decided, the decision."""
    rows = db.execute(
        "SELECT c.claim_id, c.claim_type, c.summary, c.amount_claimed, c.status,"
        " u.name AS customer_name, d.decision, d.payout"
        " FROM claims c JOIN customers u ON u.customer_id = c.customer_id"
        " LEFT JOIN decisions d ON d.claim_id = c.claim_id ORDER BY c.claim_id"
    ).fetchall()
    return [ClaimSummary(**row) for row in rows]


def load_policy(db: sqlite3.Connection, policy_id: str) -> Policy:
    """A policy with the limits of its plan."""
    policy = json.loads(
        db.execute(
            "SELECT data FROM policies WHERE policy_id = ?", (policy_id,)
        ).fetchone()["data"]
    )
    plan = db.execute("SELECT data FROM plans WHERE plan = ?", (policy["plan"],))
    return Policy(**policy, limits=Plan(**json.loads(plan.fetchone()["data"])))


def load_customer(db: sqlite3.Connection, customer_id: str) -> Customer:
    """A customer's name and claim history, without contact details."""
    row = db.execute(
        "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    return Customer(
        customer_id=row["customer_id"],
        name=row["name"],
        previous_claims=json.loads(row["previous_claims"]),
    )


def get_handler(db: sqlite3.Connection, handler_id: str) -> Handler:
    """One handler, or a 404."""
    row = db.execute(
        "SELECT * FROM handlers WHERE handler_id = ?", (handler_id,)
    ).fetchone()
    if row is None:
        raise not_found("Handler", handler_id)
    return Handler(
        **{**row, "can_approve_over_limit": bool(row["can_approve_over_limit"])}
    )


def list_handlers(db: sqlite3.Connection) -> list[Handler]:
    """All the claims handlers."""
    rows = db.execute("SELECT * FROM handlers ORDER BY handler_id").fetchall()
    return [
        Handler(
            **{**row, "can_approve_over_limit": bool(row["can_approve_over_limit"])}
        )
        for row in rows
    ]


def get_detail(db: sqlite3.Connection, claim_id: str) -> ClaimDetail:
    """The whole claim, or a 404."""
    claim = db.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if claim is None:
        raise not_found("Claim", claim_id)
    decision = db.execute(
        "SELECT * FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    payment = db.execute(
        "SELECT * FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    sign_off = db.execute(
        "SELECT s.handler_id, h.name AS handler_name, s.signed_at FROM sign_offs s"
        " JOIN handlers h ON h.handler_id = s.handler_id WHERE s.claim_id = ?",
        (claim_id,),
    ).fetchone()
    return ClaimDetail(
        **{
            **claim,
            "items": json.loads(claim["items"]),
            "documents": json.loads(claim["documents"]),
            "policy": load_policy(db, claim["policy_id"]),
            "customer": load_customer(db, claim["customer_id"]),
            "decision": Decision(**decision) if decision else None,
            "payment": Payment(**payment) if payment else None,
            "sign_off": SignOff(**sign_off) if sign_off else None,
        }
    )
