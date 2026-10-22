"""The UnderCover backend."""

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse

from backend import claims
from backend.db import DATA, ROOT, get_db, init_db
from backend.models import ClaimDetail, ClaimSummary, Handler

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
