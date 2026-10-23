"""Runs of the queue agent: its to-do list, its cap and its closing check."""

import sqlite3

from backend import claims, rules
from backend.models import ClaimSummary, Run, Todo


def get_run(db: sqlite3.Connection, run_id: int) -> Run:
    """A run with its to-do list, or a 404."""
    row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise claims.not_found("Run", str(run_id))
    todos = db.execute(
        "SELECT content, status FROM todos WHERE run_id = ? ORDER BY position",
        (run_id,),
    ).fetchall()
    return Run(
        run_id=row["id"],
        started_at=row["started_at"],
        limit=row["claim_limit"],
        status=row["status"],
        summary=row["summary"],
        todos=[Todo(**todo) for todo in todos],
    )


def get_latest(db: sqlite3.Connection) -> Run | None:
    """The most recent run, if there has been one."""
    row = db.execute("SELECT MAX(id) AS id FROM runs").fetchone()
    return None if row["id"] is None else get_run(db, row["id"])


def get_running(db: sqlite3.Connection, run_id: int) -> Run:
    """A run that is still going, or a 409."""
    run = get_run(db, run_id)
    if run.status != "running":
        raise rules.conflict(f"Run {run_id} is {run.status}")
    return run


def start_run(db: sqlite3.Connection, limit: int) -> Run:
    """Start a run that may work `limit` claims (0 for no cap), or a 409."""
    if db.execute("SELECT 1 FROM runs WHERE status = 'running'").fetchone():
        raise rules.conflict("A run is already going")
    with db:
        cursor = db.execute(
            "INSERT INTO runs (started_at, claim_limit) VALUES (?, ?)",
            (rules.now(), limit),
        )
    return get_run(db, cursor.lastrowid or 0)


def write_todos(db: sqlite3.Connection, run_id: int, todos: list[Todo]) -> Run:
    """Replace the run's to-do list."""
    get_running(db, run_id)
    with db:
        db.execute("DELETE FROM todos WHERE run_id = ?", (run_id,))
        db.executemany(
            "INSERT INTO todos VALUES (?, ?, ?, ?)",
            [(run_id, i, t.content, t.status) for i, t in enumerate(todos)],
        )
    return get_run(db, run_id)


def taken(db: sqlite3.Connection, run_id: int) -> set[str]:
    """The claims the run has started work on."""
    rows = db.execute(
        "SELECT claim_id FROM run_claims WHERE run_id = ?", (run_id,)
    ).fetchall()
    return {row["claim_id"] for row in rows}


def list_queue(db: sqlite3.Connection, run_id: int) -> list[ClaimSummary]:
    """The waiting claims the run may still work.

    A claim the run has taken that went back to the queue is always listed.
    Other waiting claims are listed while the run is under its cap.
    """
    run = get_run(db, run_id)
    started = taken(db, run_id)
    open_slot = run.limit == 0 or len(started) < run.limit
    return [
        claim
        for claim in claims.list_summaries(db)
        if claim.status == "waiting" and (claim.claim_id in started or open_slot)
    ]


def start_claim(db: sqlite3.Connection, run_id: int, claim_id: str) -> ClaimSummary:
    """Start work on a waiting claim for this run, unless the cap is reached."""
    run = get_running(db, run_id)
    started = taken(db, run_id)
    if claim_id not in started and run.limit and len(started) >= run.limit:
        raise rules.conflict(f"The run has reached its cap of {run.limit} claims")
    rules.start_claim(db, claim_id)
    with db:
        db.execute("INSERT OR IGNORE INTO run_claims VALUES (?, ?)", (run_id, claim_id))
    return claims.get_summary(db, claim_id)


def finish_run(db: sqlite3.Connection, run_id: int, summary: str) -> Run:
    """Finish the run, unless it has missed a claim it should have worked."""
    get_running(db, run_id)
    missed = [claim.claim_id for claim in list_queue(db, run_id)]
    if missed:
        raise rules.conflict(f"Claims still to work: {', '.join(missed)}")
    with db:
        db.execute(
            "UPDATE runs SET status = 'finished', summary = ? WHERE id = ?",
            (summary, run_id),
        )
    return get_run(db, run_id)


def fail_run(db: sqlite3.Connection, run_id: int, reason: str) -> None:
    """Mark a run that stopped before it finished."""
    with db:
        db.execute(
            "UPDATE runs SET status = 'failed', summary = ? WHERE id = ?",
            (reason, run_id),
        )
