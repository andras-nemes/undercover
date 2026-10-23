"""Running the UnderCover Agent in the background."""

from uuid import uuid4

from agent.main import run as run_agent
from agent.main import run_queue
from backend import rules, runs
from backend.db import connect


def work(claim_id: str) -> None:
    """Run the agent on a claim that has been started, then settle the claim."""
    reason = ""
    try:
        run_agent(claim_id, f"{claim_id}-{uuid4().hex[:8]}")
    except Exception as error:
        reason = str(error)
    db = connect()
    rules.release_claim(db, claim_id, reason)
    db.close()


def work_run(run_id: int) -> None:
    """Run the queue agent, and fail the run if it stops before it finishes."""
    reason = "The agent stopped before it finished the run"
    try:
        run_queue(run_id)
    except Exception as error:
        reason = f"The run stopped: {error}"
    db = connect()
    if runs.get_run(db, run_id).status == "running":
        runs.fail_run(db, run_id, reason)
    db.close()
