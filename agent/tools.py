"""Every tool the UnderCover agents use.

A claim agent works the one claim in its context, so it cannot touch another.
The queue agent works through a run and hands each claim to a claim agent.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from pydantic import BaseModel

from agent import api

Document = Literal["wording", "manual"]


@dataclass
class ClaimContext:
    claim_id: str


@dataclass
class QueueContext:
    run_id: int
    work: Callable[[str], str]


class Todo(BaseModel):
    content: str
    status: Literal["todo", "in_progress", "done", "left_for_handler"]


@tool
def get_claim(runtime: ToolRuntime[ClaimContext]) -> str:
    """Get your claim with its documents, the customer's policy and claim history."""
    return api.get_claim(runtime.context.claim_id)


@tool
def list_sections(document: Document) -> str:
    """List the numbered sections of the policy wording or the claims manual."""
    return api.list_sections(document)


@tool
def read_section(
    document: Document, section: int, runtime: ToolRuntime[ClaimContext]
) -> str:
    """Read one numbered section of the policy wording or the claims manual."""
    return api.read_section(runtime.context.claim_id, document, section)


@tool
def decide_claim(
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
    runtime: ToolRuntime[ClaimContext],
) -> str:
    """Record your decision on the claim. The payout is 0 unless you approve."""
    return api.decide_claim(
        runtime.context.claim_id, decision, payout, reason, policy_section
    )


@tool
def pay_claim(amount: float, runtime: ToolRuntime[ClaimContext]) -> str:
    """Pay the claim its approved payout."""
    return api.pay_claim(runtime.context.claim_id, amount)


@tool
def list_queue(runtime: ToolRuntime[QueueContext]) -> str:
    """List the waiting claims you may take, including any sent back for a retry."""
    return api.list_queue(runtime.context.run_id)


@tool
def write_todos(todos: list[Todo], runtime: ToolRuntime[QueueContext]) -> str:
    """Replace your to-do list. The handlers watch it on the dashboard."""
    return api.write_todos(
        runtime.context.run_id, [todo.model_dump() for todo in todos]
    )


@tool
def work_claim(claim_id: str, runtime: ToolRuntime[QueueContext]) -> str:
    """Hand a claim to a helper that works it afresh and reports back in a line."""
    api.start_claim(runtime.context.run_id, claim_id)
    reason = ""
    report = ""
    try:
        report = runtime.context.work(claim_id)
    except Exception as error:
        reason = str(error)
    status = json.loads(api.release_claim(claim_id, reason))["status"]
    if status == "waiting":
        return f"{claim_id} failed ({reason or 'not finished'}). Back in the queue."
    if status == "needs_handler":
        return (
            f"{claim_id} failed again ({reason or 'not finished'}). Left for a handler."
        )
    return report


@tool
def finish_run(summary: str, runtime: ToolRuntime[QueueContext]) -> str:
    """Finish the run with a short summary for the handlers."""
    return api.finish_run(runtime.context.run_id, summary)


CLAIM_TOOLS = [get_claim, list_sections, read_section, decide_claim, pay_claim]
QUEUE_TOOLS = [list_queue, write_todos, work_claim, finish_run]
