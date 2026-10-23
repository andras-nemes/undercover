"""The UnderCover backend."""

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.responses import PlainTextResponse

from backend import claims, rules, runner
from backend.db import DATA, ROOT, get_db, init_db
from backend.models import (
    ClaimDetail,
    ClaimSummary,
    Decision,
    Event,
    Handler,
    NewDecision,
    NewEvent,
    NewPayment,
    NewSignOff,
    Payment,
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


@app.get(
    "/api/policy-wording",
    operation_id="get_policy_wording",
    response_class=PlainTextResponse,
)
def get_policy_wording() -> str:
    """Get the policy wording, the contract with the customer."""
    return (DATA / "policy_wording.md").read_text(encoding="utf-8")


@app.get(
    "/api/instructions",
    operation_id="get_instructions",
    response_class=PlainTextResponse,
)
def get_instructions() -> str:
    """Get the instructions the UnderCover Agent follows."""
    return (ROOT / "backend" / "instructions.md").read_text(encoding="utf-8")


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
    rules.get_status(db, claim_id)
    runner.start(claim_id)
    background.add_task(runner.work, claim_id)
    return claims.get_detail(db, claim_id)


@app.post("/api/run-waiting", operation_id="run_waiting_claims")
def run_waiting_claims(background: BackgroundTasks, db: Db) -> list[ClaimSummary]:
    """Start the agent on every waiting claim, one after another."""
    waiting = [c for c in claims.list_summaries(db) if c.status == "waiting"]
    background.add_task(runner.work_waiting, [c.claim_id for c in waiting])
    return waiting
