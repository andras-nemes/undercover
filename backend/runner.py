"""Running the UnderCover Agent on claims in the background."""

from uuid import uuid4

from fastapi import HTTPException

from agent.main import run as run_agent
from backend import rules
from backend.db import connect


def start(claim_id: str) -> None:
    """Mark a waiting claim as in progress, or refuse with a 409."""
    db = connect()
    with db:
        started = db.execute(
            "UPDATE claims SET status = 'in_progress'"
            " WHERE claim_id = ? AND status = 'waiting'",
            (claim_id,),
        ).rowcount
    db.close()
    if not started:
        raise HTTPException(status_code=409, detail=f"Claim {claim_id} is not waiting")


def work(claim_id: str) -> None:
    """Run the agent on a claim that has been started, then settle its state."""
    db = connect()
    try:
        run_agent(claim_id, f"{claim_id}-{uuid4().hex[:8]}")
    except Exception as error:
        rules.add_event(db, claim_id, "error", f"The agent stopped: {error}")
    if rules.get_status(db, claim_id) == "in_progress":
        rules.set_status(db, claim_id, "waiting")
        db.commit()
    db.close()


def work_waiting(claim_ids: list[str]) -> None:
    """Run the agent on each of these claims in turn, skipping any no longer waiting."""
    for claim_id in claim_ids:
        try:
            start(claim_id)
        except HTTPException:
            continue
        work(claim_id)
