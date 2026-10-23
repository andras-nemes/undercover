from uuid import uuid4

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class BrokenModel(StubModel):
    """A chat model that always fails, as a provider outage would."""

    def _generate(self, *args, **kwargs):
        raise RuntimeError("model unavailable")


def call(name, **args):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"{name}-{uuid4().hex[:6]}"}],
    )


def decide(decision, payout):
    return call(
        "decide_claim",
        decision=decision,
        payout=payout,
        reason="Covered by the wording.",
        policy_section="Section 3, Trip Delay",
    )


def script(*replies):
    return StubModel(messages=iter(replies))


def approve_and_pay(payout=420.0, report="Approved and paid."):
    """The replies of a claim agent that approves a claim and pays it."""
    return [
        decide("approve", payout),
        call("pay_claim", amount=payout),
        AIMessage(content=report),
    ]
