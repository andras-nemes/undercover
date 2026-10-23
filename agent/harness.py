"""The agent harness: the model, the middleware and the loop that runs an agent.

Nothing here knows about claims. The tools, the instructions and the context an
agent works with are passed in.
"""

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolErrorMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
MODEL_TIMEOUT = 120
RESULT_LIMIT = 500

OnStep = Callable[[str, str], object]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=MODEL_TIMEOUT,
        max_retries=0,
    )


@dataclass
class Spec:
    """What makes one kind of agent: its tools, instructions and limits."""

    tools: Sequence[BaseTool]
    instructions: str
    context_schema: type
    call_limit: int
    refusals: tuple[type[Exception], ...] = ()


def create(llm: BaseChatModel, spec: Spec) -> CompiledStateGraph:
    """Build an agent.

    A model call that fails is retried with a back-off. An agent that makes more
    than `call_limit` model calls stops with an error. A tool that raises one of
    the `refusals` tells the model what went wrong; any other error stops the run.
    """
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        ModelRetryMiddleware(on_failure="error"),
        ModelCallLimitMiddleware(run_limit=spec.call_limit, exit_behavior="error"),
        ToolErrorMiddleware(
            lambda error, _: str(error) if isinstance(error, spec.refusals) else None
        ),
    ]
    return create_agent(
        llm,
        tools=spec.tools,
        system_prompt=spec.instructions,
        context_schema=spec.context_schema,
        middleware=middleware,
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


def run(
    agent: CompiledStateGraph,
    task: str,
    context: Any,
    thread_id: str,
    on_step: OnStep | None = None,
) -> str:
    """Run an agent on a task, report each step to `on_step`, return its reply."""
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": task}]},
        config={"configurable": {"thread_id": thread_id}},
        context=context,
        stream_mode="updates",
    ):
        for state in update.values():
            for message in (state or {}).get("messages", []):
                for kind, text in steps(message):
                    if on_step:
                        on_step(kind, text)
                    if kind == "finished":
                        reply = text
    return reply
