"""The UnderCover Agent: one entry point for a claim, one for the whole queue."""

from collections.abc import Callable
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

from agent import api, harness
from agent.tools import CLAIM_TOOLS, QUEUE_TOOLS, ClaimContext, QueueContext

load_dotenv(override=True)

CLAIM_CALL_LIMIT = 40
QUEUE_CALL_LIMIT = 200


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the claim agent on a claim, log its steps to the claim, return its reply."""
    spec = harness.Spec(
        CLAIM_TOOLS,
        api.get_instructions("claim"),
        ClaimContext,
        CLAIM_CALL_LIMIT,
        (api.ApiError,),
    )
    agent = harness.create(llm or harness.model(), spec)
    api.add_event(claim_id, "started", f"Started on {claim_id}")
    return harness.run(
        agent,
        f"Claim {claim_id}",
        ClaimContext(claim_id),
        thread_id,
        lambda kind, text: api.add_event(claim_id, kind, text),
    )


def run_queue(
    run_id: int,
    llm: BaseChatModel | None = None,
    claim_llm: Callable[[str], BaseChatModel] | None = None,
) -> str:
    """Run the queue agent on a run, return its reply.

    Each claim goes to a fresh claim agent; `claim_llm` gives it a model by claim id.
    """

    def work(claim_id: str) -> str:
        helper = claim_llm(claim_id) if claim_llm else None
        return run(claim_id, f"{claim_id}-{uuid4().hex[:8]}", helper)

    spec = harness.Spec(
        QUEUE_TOOLS,
        api.get_instructions("queue"),
        QueueContext,
        QUEUE_CALL_LIMIT,
        (api.ApiError,),
    )
    agent = harness.create(llm or harness.model(), spec)
    return harness.run(
        agent,
        f"Run {run_id}",
        QueueContext(run_id, work),
        f"run-{run_id}",
    )
