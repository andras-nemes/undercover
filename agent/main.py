"""The UnderCover Agent."""

import os
from contextlib import AbstractContextManager
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
RESULT_LIMIT = 500


def backend() -> AbstractContextManager[httpx.Client]:
    """Return a client for the UnderCover backend."""
    return httpx.Client(
        base_url=os.getenv("BACKEND_URL", "http://localhost:8000"), timeout=30
    )


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return the reply, or the backend's error as text."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Error {response.status_code}: {response.json()['detail']}"
    return response.text


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim with its documents, the customer's policy and claim history."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def list_sections(document: Literal["wording", "manual"]) -> str:
    """List the numbered sections of the policy wording or the claims manual."""
    return call("GET", f"/api/documents/{document}/sections")


@tool
def read_section(
    claim_id: str, document: Literal["wording", "manual"], section: int
) -> str:
    """Read one numbered section of the policy wording or the claims manual."""
    body = {"document": document, "section": section}
    return call("POST", f"/api/claims/{claim_id}/reads", body)


@tool
def decide_claim(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim. The payout is 0 unless you approve."""
    body = {
        "decision": decision,
        "payout": payout,
        "reason": reason,
        "policy_section": policy_section,
    }
    return call("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout."""
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def steps(message: BaseMessage) -> list[tuple[str, str]]:
    """Describe a message from the agent as (kind, text) steps."""
    if isinstance(message, ToolMessage):
        return [("tool_result", message.text[:RESULT_LIMIT])]
    if isinstance(message, AIMessage) and message.tool_calls:
        return [("tool_call", f"{c['name']} {c['args']}") for c in message.tool_calls]
    if isinstance(message, AIMessage):
        return [("finished", message.text)]
    return []


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim, log each step to the backend, return its reply."""

    def log(kind: str, text: str) -> None:
        call("POST", f"/api/claims/{claim_id}/events", {"kind": kind, "text": text})

    agent = create_agent(
        llm or model(),
        tools=[get_claim, list_sections, read_section, decide_claim, pay_claim],
        system_prompt=call("GET", "/api/instructions/claim"),
    )
    log("started", f"Started on {claim_id}")
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for state in update.values():
            for message in state["messages"]:
                for kind, text in steps(message):
                    log(kind, text)
                    if kind == "finished":
                        reply = text
    return reply


def run_queue(run_id: int) -> str:
    """Run the queue agent. Built in Phase 4 of docs/PLAN_HARNESS.md."""
    raise NotImplementedError(run_id)
