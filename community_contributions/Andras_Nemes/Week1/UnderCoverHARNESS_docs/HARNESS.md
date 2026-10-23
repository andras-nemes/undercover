# UnderCover harness build

## What I did

I built the Week 1 Day 5 harness for UnderCover Travel Insurance with Claude Code, extending the pilot from Week 1 Day 3. I worked from `docs/HARNESS.md`, the brief from UnderCover's platform team, which asks for seven things: a queue agent that works the whole queue, a to-do list the handlers can see, a claim helper (a subagent) per claim, lookup of the policy wording and the claims manual by section, automatic recovery from a failed attempt, DeepSeek V4.1 Flash as the default model, and two sets of instructions.

**The plan.** Claude Code read the pilot's code and the brief, then wrote `docs/PLAN_HARNESS.md`: the design decisions, the backend API changes, and six phases, each with checkbox success criteria. I reviewed it before any build started.

**A code review, and a restructure.** Partway through the build I reviewed the agent code against the plan and found it fell short of what I'd expect in a pull request: more than twenty hardcoded backend URLs across three files, two different ways of calling the backend, the harness (the model and its middleware) mixed in with claims-specific logic, and instructions written as rigid step-by-step scripts rather than a goal an agent can reason about. I wrote up the review and asked Claude Code to fix it, investigate whether the same problems existed in the backend and dashboard, and update the project's own standards so it would not happen again.

It did: `agent/api.py` is now the one module that calls the backend; `agent/harness.py` holds the model, the retry and call-limit middleware, and the run loop, with no knowledge of claims; `agent/tools.py` holds every tool for both agents, reached through LangChain's `ToolRuntime`; and both instruction files were rewritten to state a goal and what must hold, not a fixed procedure. `docs/CODE_STANDARDS.md` and `docs/PROCESS.md` were extended with the standards this should have caught the first time: one module per external service, the harness kept separate from the domain, and a check against those standards as part of finishing a phase, not just a check that the tests pass.

**The build.** Six phases, each checked, ticked and committed before the next:

1. **Document lookup.** The policy wording and the claims manual, split into numbered sections and served one at a time. Every section a claim helper reads is recorded on the claim.
2. **Runs, a to-do list, a cap and recovery** — enforced by the backend, not trusted to the model. A run can be capped at a number of claims. A claim a helper leaves unfinished goes back to the queue once, and is left for a handler the second time.
3. **The claim helper**: a fresh agent per attempt, with `get_claim`, `list_sections`, `read_section`, `decide_claim` and `pay_claim`, and the recovery middleware from LangChain (`ModelRetryMiddleware`, `ModelCallLimitMiddleware`) so a stuck or looping model fails cleanly instead of burning tokens.
4. **The queue agent**: lists the waiting claims, keeps the to-do list, hands each claim to a fresh helper, and finishes with a summary. It never reads a claim or a document itself, so its own context stays small for the whole run.
5. **The dashboard**: a run panel on the queue page with the to-do list and its chips, a "What the agent read" panel on the claim page, the new "left for a handler" state throughout, and both sets of instructions.
6. **A live run**, proving the whole chain end to end.

**Results.** `npm run check` passes in full: ruff, pyright and pytest (99.7% coverage) on the Python side; ESLint, Prettier, `tsc` and vitest (100% statement coverage) on the TypeScript side; and the Playwright end-to-end suite. No test calls a model — Python tests use a stub, and the end-to-end tests set state through the same API the agents use.

**The live run.** I capped a run at five claims and started it from the dashboard, on the free model route so it cost nothing. Four claims were worked with no click on any single one: a trip delay and a baggage claim approved and paid, a baggage delay approved and paid, and an emergency medical claim approved at $3,750.00 — correctly left waiting for a handler's sign-off, since it is over the $1,000.00 limit. The fifth claim then hit the free route's daily request quota. Rather than hide this, I think it is the more convincing result: the queue agent's own next step hit the same quota and the run ended `failed` with a clear reason, exactly as the recovery design intends when a model is down for good; and a retry on the fifth claim hit the quota again and correctly left it for a handler after its second failure, with both attempts recorded on the claim. Every rule this run could exercise held under a genuine provider failure, not a stub.

**What I did not do.** I did not open `data/evals/`, so I have not scored the agent against the handlers' decisions. There is still no sign-in, no real payments, no messages to customers, and no way yet for a handler to send a claim left for them back into the queue.

## The UI in action

These screenshots are from the dashboard with the live run's real outcome above, reproduced through the backend's own rules rather than replaying the run, so the figures and reasoning are genuine.

**The queue, with a run finished.** The run panel's to-do list, each item's status as a chip, and the queue below it with the "Left for a handler" state and its Raspberry chip.

![The claims queue with a finished run's to-do list](images/queue-with-run.png)

**A decided claim, and what the agent read.** CLM-1001, approved and paid, with its reasoning, its policy section, and the new panel listing exactly which sections of the wording and the manual the agent consulted.

![A decided claim with its reasoning and the sections the agent read](images/claim-reads.png)

**Waiting for sign-off.** CLM-1003, approved at $3,750.00 — over the limit — with the payment blocked until a handler signs off, and the sections the agent read for an emergency medical claim.

![An approval over the limit waiting for a handler's sign-off](images/sign-off-waiting.png)

**Left for a handler.** CLM-1005, after two failed attempts. Both attempts are recorded in order in the agent's steps, exactly as the recovery rule intends.

![A claim left for a handler after two failed attempts, with both attempts in its step log](images/left-for-handler.png)

**Both sets of instructions.** "Running the queue" and "Working a claim", each stating a goal and what must hold rather than a fixed script.

![Both sets of agent instructions, read only](images/instructions.png)

**Dark mode**, in the UnderCover brand.

![The claims queue with a finished run, in dark mode](images/queue-dark.png)

## My takeaways

- **A subagent per claim keeps the orchestrator's context flat.** The queue agent only ever sees a helper's one-line report, never a claim's documents or sections. Claim 20 costs the queue agent no more context than claim 1, which matters once a run is no longer capped at five.
- **Enforce recovery in the backend, not in the model's good behavior.** The cap, the retry-once-then-hand-off rule, and the check that a run cannot finish while it still owes a claim are all backend rules the agent cannot talk its way around. The live run proved this by accident: a real provider outage, not a test, exercised every one of them correctly.
- **A code review partway through a build is worth doing before the build is "done," not after.** The issues it found — duplicated backend calls, the harness mixed with domain logic — are exactly the kind that are cheap to fix while there are two agents and expensive once there are five. Writing the fix back into the project's own standards, not just the code, is what keeps it from recurring.
- **The free model route is a real route, with a real daily limit.** It is free, but not infinite, and it is slower and more heavily shared than the paid default. It is the right choice for a bounded check that should cost nothing; a full queue or a timed comparison needs the paid model.
- **A stale fixture can outlive the schema it was built for.** While checking this build I found the end-to-end suite's database file was named from the test runner's process id, which Windows can reuse quickly enough to pick up a leftover file from an older run, with an older schema silently kept. Worth watching for in any suite that reuses a file by name instead of guaranteeing it is new.
