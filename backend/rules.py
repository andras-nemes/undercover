"""Decisions, payments, sign-off and events: the rules of the claims queue."""

import sqlite3
from datetime import UTC, datetime

from fastapi import HTTPException

from backend import claims
from backend.models import Decision, Event, NewDecision, Payment, Status

MAX_ATTEMPTS = 2


def now() -> str:
    """The current time in UTC, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def conflict(detail: str) -> HTTPException:
    """Build the 409 for an action the claim's state does not allow."""
    return HTTPException(status_code=409, detail=detail)


def approval_limit(db: sqlite3.Connection) -> float:
    """The payout above which a handler must sign off."""
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'payout_approval_limit'"
    ).fetchone()
    return row["value"]


def set_status(db: sqlite3.Connection, claim_id: str, status: Status) -> None:
    """Move a claim to a new state."""
    db.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id))


def get_status(db: sqlite3.Connection, claim_id: str) -> Status:
    """The claim's state, or a 404."""
    row = db.execute(
        "SELECT status FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise claims.not_found("Claim", claim_id)
    return row["status"]


def start_claim(db: sqlite3.Connection, claim_id: str) -> None:
    """Move a waiting claim to in progress, or refuse with a 409."""
    get_status(db, claim_id)
    with db:
        started = db.execute(
            "UPDATE claims SET status = 'in_progress'"
            " WHERE claim_id = ? AND status = 'waiting'",
            (claim_id,),
        ).rowcount
    if not started:
        raise conflict(f"Claim {claim_id} is not waiting")


def release_claim(db: sqlite3.Connection, claim_id: str, reason: str) -> None:
    """Settle a claim after an agent has worked on it.

    A claim still in progress was not finished: the first time it goes back to
    waiting, the second time it is left for a handler.
    """
    if get_status(db, claim_id) != "in_progress":
        return
    row = db.execute(
        "SELECT failures FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    failures = row["failures"] + 1
    left = failures >= MAX_ATTEMPTS
    with db:
        db.execute(
            "UPDATE claims SET failures = ? WHERE claim_id = ?", (failures, claim_id)
        )
        set_status(db, claim_id, "needs_handler" if left else "waiting")
    why = reason or "the agent stopped before it finished"
    outcome = "Left for a handler." if left else "Back in the queue."
    add_event(db, claim_id, "error", f"Attempt {failures} failed: {why}. {outcome}")


def decide(db: sqlite3.Connection, claim_id: str, body: NewDecision) -> Decision:
    """Record the agent's decision. Approvals over the limit wait for sign-off."""
    get_status(db, claim_id)
    payout = round(body.payout, 2)
    if (body.decision == "approve") != (payout > 0):
        raise HTTPException(
            status_code=422, detail="Only an approval has a payout above 0"
        )
    if db.execute("SELECT 1 FROM decisions WHERE claim_id = ?", (claim_id,)).fetchone():
        raise conflict(f"Claim {claim_id} already has a decision")
    with db:
        db.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
            (claim_id, body.decision, payout, body.reason, body.policy_section),
        )
        if body.decision != "approve":
            set_status(db, claim_id, "decided")
        elif payout > approval_limit(db):
            set_status(db, claim_id, "awaiting_sign_off")
    return Decision(**{**body.model_dump(), "payout": payout})


def pay(db: sqlite3.Connection, claim_id: str, amount: float) -> Payment:
    """Pay an approved claim. Over the limit, only after a handler has signed off."""
    get_status(db, claim_id)
    decision = db.execute(
        "SELECT decision, payout FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if decision is None or decision["decision"] != "approve":
        raise conflict(f"Claim {claim_id} has no approval to pay")
    if db.execute("SELECT 1 FROM payments WHERE claim_id = ?", (claim_id,)).fetchone():
        raise conflict(f"Claim {claim_id} is already paid")
    if round(amount, 2) != decision["payout"]:
        raise conflict(f"The approved payout is ${decision['payout']:,.2f}")
    signed_off = db.execute(
        "SELECT 1 FROM sign_offs WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if decision["payout"] > approval_limit(db) and not signed_off:
        raise conflict(f"A payout over ${approval_limit(db):,.2f} needs a sign-off")
    paid_at = now()
    with db:
        db.execute(
            "INSERT INTO payments VALUES (?, ?, ?)",
            (claim_id, decision["payout"], paid_at),
        )
        set_status(db, claim_id, "decided")
    return Payment(amount=decision["payout"], paid_at=paid_at)


def sign_off(db: sqlite3.Connection, claim_id: str, handler_id: str) -> None:
    """Record a handler's sign-off and release the payment."""
    handler = claims.get_handler(db, handler_id)
    if get_status(db, claim_id) != "awaiting_sign_off":
        raise conflict(f"Claim {claim_id} is not waiting for sign-off")
    if not handler.can_approve_over_limit:
        raise HTTPException(status_code=403, detail=f"{handler.name} cannot sign off")
    payout = db.execute(
        "SELECT payout FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()["payout"]
    with db:
        db.execute(
            "INSERT INTO sign_offs VALUES (?, ?, ?)", (claim_id, handler_id, now())
        )
    pay(db, claim_id, payout)


def add_event(db: sqlite3.Connection, claim_id: str, kind: str, text: str) -> Event:
    """Record one step of the agent's work."""
    get_status(db, claim_id)
    created_at = now()
    with db:
        db.execute(
            "INSERT INTO events (claim_id, kind, text, created_at) VALUES (?, ?, ?, ?)",
            (claim_id, kind, text, created_at),
        )
    return Event(kind=kind, text=text, created_at=created_at)


def list_events(db: sqlite3.Connection, claim_id: str) -> list[Event]:
    """The agent's steps on a claim, oldest first."""
    get_status(db, claim_id)
    rows = db.execute(
        "SELECT kind, text, created_at FROM events WHERE claim_id = ? ORDER BY id",
        (claim_id,),
    ).fetchall()
    return [Event(**row) for row in rows]
