"""Every call the agents make to the UnderCover backend."""

import os
from contextlib import AbstractContextManager
from typing import Any

import httpx


class ApiError(Exception):
    """The backend refused a request."""

    def __init__(self, status: int, detail: Any) -> None:
        super().__init__(f"Error {status}: {detail}")


def backend() -> AbstractContextManager[httpx.Client]:
    """Return a client for the UnderCover backend."""
    return httpx.Client(
        base_url=os.getenv("BACKEND_URL", "http://localhost:8000"), timeout=30
    )


def request(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return the reply, or raise the backend's refusal."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        raise ApiError(response.status_code, response.json()["detail"])
    return response.text


def get_instructions(agent: str) -> str:
    """The instructions of the "queue" or the "claim" agent."""
    return request("GET", f"/api/instructions/{agent}")


def get_claim(claim_id: str) -> str:
    """A claim with its documents, policy and the customer's history."""
    return request("GET", f"/api/claims/{claim_id}")


def list_sections(document: str) -> str:
    """The numbered sections of the "wording" or the "manual"."""
    return request("GET", f"/api/documents/{document}/sections")


def read_section(claim_id: str, document: str, section: int) -> str:
    """One section of a document, noted as read on the claim."""
    body = {"document": document, "section": section}
    return request("POST", f"/api/claims/{claim_id}/reads", body)


def decide_claim(
    claim_id: str, decision: str, payout: float, reason: str, policy_section: str
) -> str:
    """Record the decision on a claim."""
    body = {
        "decision": decision,
        "payout": payout,
        "reason": reason,
        "policy_section": policy_section,
    }
    return request("POST", f"/api/claims/{claim_id}/decision", body)


def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim."""
    return request("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


def add_event(claim_id: str, kind: str, text: str) -> str:
    """Record one step of the agent's work on a claim."""
    return request(
        "POST", f"/api/claims/{claim_id}/events", {"kind": kind, "text": text}
    )


def list_queue(run_id: int) -> str:
    """The waiting claims a run may still work."""
    return request("GET", f"/api/runs/{run_id}/queue")


def write_todos(run_id: int, todos: list[dict[str, str]]) -> str:
    """Replace the to-do list of a run."""
    return request("PUT", f"/api/runs/{run_id}/todos", {"todos": todos})


def start_claim(run_id: int, claim_id: str) -> str:
    """Start work on a waiting claim for a run."""
    return request("POST", f"/api/runs/{run_id}/claims/{claim_id}/start")


def release_claim(claim_id: str, reason: str) -> str:
    """Settle a claim after work on it, and return it with its new state."""
    return request("POST", f"/api/claims/{claim_id}/release", {"reason": reason})


def finish_run(run_id: int, summary: str) -> str:
    """Finish a run with a summary for the handlers."""
    return request("POST", f"/api/runs/{run_id}/finish", {"summary": summary})
