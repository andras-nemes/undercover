import pytest
from langchain_core.messages import AIMessage
from pydantic import Field

from agent import main
from agent.tests.stubs import (
    BrokenModel,
    StubModel,
    approve_and_pay,
    call,
    script,
)


@pytest.fixture(autouse=True)
def quick_retries(use_backend, monkeypatch):
    """Start runs whose agent does nothing, and skip the model retry back-off."""
    monkeypatch.setattr("backend.runner.work_run", lambda run_id: None)
    monkeypatch.setattr("time.sleep", lambda seconds: None)


def todos(*items):
    return call("write_todos", todos=[{"content": c, "status": s} for c, s in items])


def start_run(client, limit):
    return client.post("/api/runs", json={"limit": limit}).json()["run_id"]


def helpers(attempts, on_start=None):
    """A model factory: each call hands out the next scripted attempt for a claim."""
    queues = {claim_id: list(replies) for claim_id, replies in attempts.items()}

    def make(claim_id):
        if on_start:
            on_start(claim_id)
        return queues[claim_id].pop(0)

    return make


def decided(client):
    claims = client.get("/api/claims").json()
    return {c["claim_id"]: c["status"] for c in claims}


def test_the_queue_agent_works_the_claims_and_keeps_the_list(use_backend):
    run_id = start_run(use_backend, 3)
    snapshots = {}

    def snapshot(claim_id):
        snapshots[claim_id] = use_backend.get("/api/runs/latest").json()["todos"]

    ids = ["CLM-1001", "CLM-1002", "CLM-1003"]
    plan = [(i, "todo") for i in ids]
    replies = [call("list_queue"), todos(*plan)]
    for number, claim_id in enumerate(ids):
        marked = [
            (i, "done" if n < number else "in_progress" if n == number else "todo")
            for n, i in enumerate(ids)
        ]
        replies += [todos(*marked), call("work_claim", claim_id=claim_id)]
    replies += [
        todos(*[(i, "done") for i in ids]),
        call("finish_run", summary="Three claims approved."),
        AIMessage(content="Finished."),
    ]
    attempts = {i: [script(*approve_and_pay())] for i in ids}
    main.run_queue(run_id, script(*replies), helpers(attempts, snapshot))

    run = use_backend.get("/api/runs/latest").json()
    assert run["status"] == "finished"
    assert run["summary"] == "Three claims approved."
    assert [t["status"] for t in run["todos"]] == ["done"] * 3
    assert decided(use_backend)["CLM-1003"] == "decided"
    assert [t["status"] for t in snapshots["CLM-1002"]] == [
        "done",
        "in_progress",
        "todo",
    ]


def test_the_cap_leaves_the_other_claims_waiting(use_backend):
    run_id = start_run(use_backend, 2)
    replies = [
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1002"),
        call("work_claim", claim_id="CLM-1003"),
        call("finish_run", summary="Two claims."),
        AIMessage(content="Finished."),
    ]
    attempts = {i: [script(*approve_and_pay())] for i in ("CLM-1001", "CLM-1002")}
    main.run_queue(run_id, script(*replies), helpers(attempts))
    states = decided(use_backend)
    assert states["CLM-1003"] == "waiting"
    assert list(states.values()).count("waiting") == 23
    assert use_backend.get("/api/runs/latest").json()["status"] == "finished"


def test_a_failed_claim_does_not_stop_the_run_and_is_tried_again(use_backend):
    run_id = start_run(use_backend, 2)
    replies = [
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1002"),
        call("work_claim", claim_id="CLM-1001"),
        call("finish_run", summary="Two claims."),
        AIMessage(content="Finished."),
    ]
    attempts = {
        "CLM-1001": [BrokenModel(messages=iter([])), script(*approve_and_pay())],
        "CLM-1002": [script(*approve_and_pay())],
    }
    main.run_queue(run_id, script(*replies), helpers(attempts))
    states = decided(use_backend)
    assert states["CLM-1001"] == "decided"
    assert states["CLM-1002"] == "decided"
    events = use_backend.get("/api/claims/CLM-1001/events").json()
    kinds = [e["kind"] for e in events]
    assert kinds.count("started") == 2
    assert "Attempt 1 failed: model unavailable" in events[1]["text"]
    assert use_backend.get("/api/runs/latest").json()["status"] == "finished"


def test_a_claim_that_fails_twice_is_left_for_a_handler(use_backend):
    run_id = start_run(use_backend, 1)
    replies = [
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1001"),
        todos(("CLM-1001", "left_for_handler")),
        call("finish_run", summary="One claim left for a handler."),
        AIMessage(content="Finished."),
    ]
    broken = [BrokenModel(messages=iter([])), BrokenModel(messages=iter([]))]
    main.run_queue(run_id, script(*replies), helpers({"CLM-1001": broken}))
    assert decided(use_backend)["CLM-1001"] == "needs_handler"
    run = use_backend.get("/api/runs/latest").json()
    assert run["status"] == "finished"
    assert run["todos"] == [{"content": "CLM-1001", "status": "left_for_handler"}]


def test_a_helper_that_ends_without_deciding_counts_as_a_failure(use_backend):
    run_id = start_run(use_backend, 1)
    replies = [
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1001"),
        call("finish_run", summary="Done."),
        AIMessage(content="Finished."),
    ]
    idle = [script(AIMessage(content="Nothing to do.")) for _ in range(2)]
    main.run_queue(run_id, script(*replies), helpers({"CLM-1001": idle}))
    assert decided(use_backend)["CLM-1001"] == "needs_handler"


def test_the_queue_agent_cannot_finish_while_it_owes_a_claim(use_backend):
    run_id = start_run(use_backend, 1)
    replies = [
        call("finish_run", summary="Too early."),
        call("work_claim", claim_id="CLM-1001"),
        call("finish_run", summary="Now done."),
        AIMessage(content="Finished."),
    ]
    attempts = {"CLM-1001": [script(*approve_and_pay())]}
    main.run_queue(run_id, script(*replies), helpers(attempts))
    run = use_backend.get("/api/runs/latest").json()
    assert run["status"] == "finished"
    assert run["summary"] == "Now done."


def test_the_queue_agent_sees_only_the_helpers_reports(use_backend):
    run_id = start_run(use_backend, 1)
    story = use_backend.get("/api/claims/CLM-1001").json()["story"][:40]

    class Recorder(StubModel):
        seen: list[str] = Field(default_factory=list)

        def _generate(self, messages, *args, **kwargs):
            self.seen = [str(m.content) for m in messages]
            return super()._generate(messages, *args, **kwargs)

    queue = Recorder(
        messages=iter(
            [
                call("work_claim", claim_id="CLM-1001"),
                call("finish_run", summary="Done."),
                AIMessage(content="Finished."),
            ]
        )
    )
    helper = [script(call("get_claim"), *approve_and_pay(report="CLM-1001 paid $420"))]
    main.run_queue(run_id, queue, helpers({"CLM-1001": helper}))
    seen = " ".join(queue.seen)
    assert "CLM-1001 paid $420" in seen
    assert story not in seen


def test_the_queue_agents_system_prompt_is_the_backends_instructions(
    use_backend, monkeypatch
):
    seen = {}
    create = main.harness.create

    def spy(*args, **kwargs):
        seen["instructions"] = args[1].instructions
        return create(*args, **kwargs)

    monkeypatch.setattr(main.harness, "create", spy)
    run_id = start_run(use_backend, 1)
    main.run_queue(run_id, script(AIMessage(content="Done.")))
    assert seen["instructions"] == use_backend.get("/api/instructions/queue").text
