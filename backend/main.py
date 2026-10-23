"""The UnderCover backend."""

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.responses import PlainTextResponse

from backend import claims, documents, rules, runner, runs
from backend.db import ROOT, get_db, init_db
from backend.models import (
    ClaimDetail,
    ClaimSummary,
    Decision,
    Event,
    Handler,
    NewDecision,
    NewEvent,
    NewFinish,
    NewPayment,
    NewRead,
    NewRelease,
    NewRun,
    NewSignOff,
    NewTodos,
    Payment,
    Run,
    Section,
)

Db = Annotated[sqlite3.Connection, Depends(get_db)]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create and seed the database on first start."""
    init_db()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List every claim in the queue with its state."""
    return claims.list_summaries(db)


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> ClaimDetail:
    """Get one claim with its policy, customer, decision and payment."""
    return claims.get_detail(db, claim_id)


@app.get("/api/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: str) -> list[Section]:
    """List the numbered sections of the policy wording or the claims manual."""
    return documents.list_sections(document)


@app.post(
    "/api/claims/{claim_id}/reads",
    operation_id="read_section",
    response_class=PlainTextResponse,
)
def read_section(claim_id: str, body: NewRead, db: Db) -> str:
    """Read one section of the wording or the manual, noted as read on the claim."""
    return documents.read_section(db, claim_id, body.document, body.section)


@app.get(
    "/api/instructions/{agent}",
    operation_id="get_instructions",
    response_class=PlainTextResponse,
)
def get_instructions(agent: str) -> str:
    """Get the instructions of the queue agent or the claim agent."""
    if agent not in ("queue", "claim"):
        raise claims.not_found("Instructions", agent)
    return (ROOT / "backend" / f"instructions_{agent}.md").read_text(encoding="utf-8")


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(db: Db) -> list[Handler]:
    """List the claims handlers."""
    return claims.list_handlers(db)


@app.get("/api/claims/{claim_id}/events", operation_id="list_events")
def list_events(claim_id: str, db: Db) -> list[Event]:
    """List the agent's steps on a claim, oldest first."""
    return rules.list_events(db, claim_id)


@app.post("/api/claims/{claim_id}/events", operation_id="add_event")
def add_event(claim_id: str, body: NewEvent, db: Db) -> Event:
    """Record one step of the agent's work on a claim."""
    return rules.add_event(db, claim_id, body.kind, body.text)


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, body: NewDecision, db: Db) -> Decision:
    """Record the decision on a claim: approve, decline or refer."""
    return rules.decide(db, claim_id, body)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, body: NewPayment, db: Db) -> Payment:
    """Pay an approved claim the amount given, once any sign-off it needs is done."""
    return rules.pay(db, claim_id, body.amount)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, body: NewSignOff, db: Db) -> ClaimDetail:
    """Sign off an approval over the limit as a handler and release its payment."""
    rules.sign_off(db, claim_id, body.handler_id)
    return claims.get_detail(db, claim_id)


@app.post("/api/claims/{claim_id}/run", operation_id="run_agent")
def run_agent(claim_id: str, background: BackgroundTasks, db: Db) -> ClaimDetail:
    """Start the agent on a waiting claim."""
    rules.start_claim(db, claim_id)
    background.add_task(runner.work, claim_id)
    return claims.get_detail(db, claim_id)


@app.post("/api/claims/{claim_id}/release", operation_id="release_claim")
def release_claim(claim_id: str, body: NewRelease, db: Db) -> ClaimSummary:
    """Settle a claim after work on it: one still in progress failed."""
    rules.release_claim(db, claim_id, body.reason)
    return claims.get_summary(db, claim_id)


@app.post("/api/runs", operation_id="start_run")
def start_run(body: NewRun, background: BackgroundTasks, db: Db) -> Run:
    """Start the queue agent on the waiting claims, with a cap (0 for none)."""
    run = runs.start_run(db, body.limit)
    background.add_task(runner.work_run, run.run_id)
    return run


@app.get("/api/runs/latest", operation_id="get_latest_run")
def get_latest_run(db: Db) -> Run | None:
    """Get the most recent run with its to-do list, or null."""
    return runs.get_latest(db)


@app.get("/api/runs/{run_id}/queue", operation_id="list_queue")
def list_queue(run_id: int, db: Db) -> list[ClaimSummary]:
    """List the waiting claims this run may still work."""
    return runs.list_queue(db, run_id)


@app.put("/api/runs/{run_id}/todos", operation_id="write_todos")
def write_todos(run_id: int, body: NewTodos, db: Db) -> Run:
    """Replace the to-do list of a run."""
    return runs.write_todos(db, run_id, body.todos)


@app.post("/api/runs/{run_id}/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(run_id: int, claim_id: str, db: Db) -> ClaimSummary:
    """Start work on a waiting claim for a run, unless its cap is reached."""
    return runs.start_claim(db, run_id, claim_id)


@app.post("/api/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, body: NewFinish, db: Db) -> Run:
    """Finish a run with a summary, unless it has missed a claim."""
    return runs.finish_run(db, run_id, body.summary)
