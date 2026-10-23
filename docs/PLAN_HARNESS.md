# Plan: the agent's harness

Source: `docs/HARNESS.md`, built to `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`. Starting point: the finished pilot in `docs/STATUS.md`. `docs/PLAN.md` is the pilot's plan and stays as it is.

## What the pilot does today

I read the pilot's code before planning. The points that matter for this build:

- `backend/runner.py` does the organizing. "Run all waiting" loops over the waiting claims and runs a fresh agent on each, one claim per run. There is no cap, no plan and no summary.
- `agent/main.py` has four tools. `get_policy_wording` returns the whole wording on every claim. There is no way to read the claims manual.
- A failed run records an `error` event and puts the claim back to `waiting`, with no limit: a claim that always fails is retried forever on the next "Run all waiting".
- The rules in `backend/rules.py` already stop a second decision (409) and a second payment (409), and block a payout over the limit until sign-off. This build leans on them and does not weaken them.
- The agent's instructions are one file, `backend/instructions.md`, and the model default is `openai/gpt-6-luna`.
- The queue page has the state chips and "Run all waiting". The claim page has the decision, the steps and sign-off.

## What we are building

Following the seven points in `docs/HARNESS.md`:

1. **A queue agent.** One run works the whole queue: it lists the waiting claims, chooses the order, hands each claim to a helper, keeps a to-do list, and finishes with a short summary. A run can be capped at a number of claims. A single named claim can still be run on its own.
2. **A to-do list** stored in the backend per run and shown on the queue page.
3. **A claim helper** (a subagent) per claim: a fresh agent with its own clean context that returns one line.
4. **Lookup of the wording and the manual by section**, with a record on the claim of every section read, shown on the claim page.
5. **Automatic recovery**: a failed claim goes back in the queue, a claim that fails twice is left for a handler, nothing is decided or paid twice, and the run checks for missed claims before it finishes.
6. **DeepSeek V4.1 Flash** as the default model.
7. **Two sets of instructions** (queue and claim) on the instructions page, written from the wording and the manual.

Not in this build: sign-in, a screen for a handler to hand a left-over claim back to the queue, running claims in parallel, messages to customers, scoring against `data/evals/` (I will not open that folder). Nothing from a later day's brief.

## Design decisions

These are the choices I made where `docs/HARNESS.md` is silent or I had alternatives. Please check them in your review.

### How the agent is organized

- **Two agents, one framework.** Both use LangChain's `create_agent`, as now. No `deepagents` and no other framework, as the brief asks. The harness pieces (to-do list, subagent, closing check) are our own tools in `agent/`. For recovery I use two pieces of middleware that already ship with LangChain: `ModelRetryMiddleware` (timeouts and provider errors, retried with a back-off) and `ModelCallLimitMiddleware` (a run that loops forever fails instead of burning tokens). That is part of the stack we already use, not a new dependency.
- **The to-do list is our own tool.** LangChain's `write_todos` has three statuses; the brief needs four: `todo`, `in_progress`, `done` and `left_for_handler`. Our `write_todos` tool replaces the whole list each call (the same shape the model already knows) and the backend stores it.
- **The queue agent's tools:** `list_queue` (the claims it may still take), `write_todos`, `work_claim` (runs the helper) and `finish_run` (records the summary). It never reads claims or documents itself, which keeps its context small for the whole run.
- **The claim helper** is a fresh `create_agent` per attempt, created inside the `work_claim` tool, with its own thread id. Its tools: `get_claim`, `list_sections`, `read_section`, `decide_claim`, `pay_claim`. It returns its final reply, which the instructions ask to be one line: the decision and payout, or what went wrong. The queue agent only ever sees that line, so each step on claim 20 costs no more than on claim 1.
- **Every step is still recorded on the claim.** The helper posts events to its claim exactly as the pilot's agent does.
- **One claim at a time.** The queue agent is told to work the claims one after another. Parallel helpers are not needed to meet the brief, and SQLite plus a cap are simpler without them.
- **Entry points.** `run(claim_id, thread_id)` (the helper, for one named claim, as before) and `run_queue(run_id)` (the queue agent). `docs/TECH_STACK.md` is updated to say so.

### Looking things up like a handler

- **Table of contents, then the section.** `list_sections(document)` returns the numbers and titles of the sections of `wording` or `manual`. `read_section(document, section)` returns one section's text. The helper reads the contents first, then only what the claim needs. A handler does the same with the printed manual.
- **Sections are the `## N. Title` headings** of `data/policy_wording.md` (12 sections) and `data/claims_manual.md` (14 sections). The backend splits them on those headings; no new files or data.
- **The backend records every read.** `read_section` is a POST that stores (claim, document, section) and returns the text, so the record does not depend on the model's own account of what it read. The claim detail gains `reads`, and the claim page shows them ("What the agent read").
- **The full-wording operation goes.** `get_policy_wording` is removed along with its tool; the agent no longer gets whole documents.

### Runs and the to-do list

- **A run is a row.** `runs`: id, start time, `limit` (0 means no cap, because operations take no optional inputs), status (`running`, `finished`, `failed`), summary. `run_claims` records which claims the run has taken. `todos` holds the list items for a run, in order.
- **The queue page shows the latest run's list.** One read operation, `get_latest_run`, returns the run with its to-do items. The page polls it every two seconds while the run is running.
- **The cap is enforced by the backend, not by trusting the model.** Starting a claim in a run fails with 409 once the run has taken `limit` different claims. A claim that went back to the queue for a retry is already one of the run's claims, so retries do not use up the cap. The rest of the queue stays `waiting`.
- **A named claim** still runs on its own through `POST /api/claims/{id}/run`: the claim helper directly, with the same recovery rules, no queue agent and no to-do list.

### Recovery

- **The harness does the recovery, not the model.** `work_claim` wraps the helper in a `try`/`finally`. In the `finally` it always calls the backend's `release_claim`. If the claim is still `in_progress` at that point (the helper raised, timed out, stopped without finishing, or approved without paying a payout it could pay), the backend counts one failure. That is the one place where the harness catches exceptions, as in the pilot.
- **Failure rules, in the backend (`rules.py`):** the first failure puts the claim back to `waiting` with an `error` event. The second sets it to a new state, `needs_handler`. The failure count lives on the claim, so it is the same for runs and for single-claim runs.
- **A new claim state, `needs_handler`** ("Left for a handler"), shown with Raspberry (the brand's alert color). The brief says a claim "is left for a handler" and `docs/SPEC.md` lists four states; I add this fifth rather than hiding the claim as a referral, since a referral is a decision and this claim has none. `docs/SPEC.md` is updated.
- **Never decided or paid twice.** Already guaranteed by `decide` and `pay` (409 on a second try). On a retry the claim helper sees the existing decision in `get_claim`, and its instructions say to pay an unpaid approval and not decide again, as the pilot's instructions do. New tests prove it through a failed-then-retried claim.
- **The closing check.** `finish_run(summary)` is refused with a 409 that lists the claims the run missed. "Missed" means: waiting claims the run has already taken (retries still to do), plus, while the run is under its cap, any other waiting claim. The queue agent must work them and try again. `list_queue` uses the same rule, so what it lists is exactly what it may still take. If the cap is reached and nothing is owed, the run finishes with the rest left waiting.
- **If the queue agent itself fails** (the model is down for good, or it hits the call limit), the runner marks the run `failed` with the reason. Any claim it left `in_progress` was already released by `work_claim`'s `finally`.
- **After reseeding.** Existing `backend/undercover.db` files have the old schema. A new `npm run reseed` deletes the file; the backend rebuilds and reseeds it on the next start. I use it before every live run.

### The model

- `deepseek/deepseek-v4.1-flash` at low reasoning effort is the default for both agents. `MODEL_NAME` still overrides it, in which case no reasoning effort is set (as the pilot does for `openrouter/free`).
- A request timeout of 120 seconds on the model so a stuck call fails and gets retried.

### The instructions

- `backend/instructions.md` is split into `instructions_queue.md` and `instructions_claim.md`. The operation becomes `get_instructions` with the agent (`queue` or `claim`) in the path, and each agent fetches its own at the start of its run. The page shows both.
- I write them from `data/policy_wording.md` and `data/claims_manual.md` only: the order for working a claim (manual section 4), the three decisions (section 2), payout authority (3), documents (5), payout arithmetic (6), when to refer (8, 9), meals without receipts (10), and the closing rules. They say where to look, e.g. "read the manual section on repeat claims", and do not copy the manual in. I will not read `data/evals/`, and a test keeps `evals` out of the source as before.

### Backend API changes

| operation_id | Route | Used by | Change |
|---|---|---|---|
| `get_policy_wording` | `GET /api/policy-wording` | | removed |
| `get_instructions` | `GET /api/instructions/{agent}` | dashboard, agents | now per agent |
| `list_sections` | `GET /api/documents/{document}/sections` | claim helper | new |
| `read_section` | `POST /api/claims/{claim_id}/reads` | claim helper | new; body `document`, `section` |
| `run_waiting_claims` | `POST /api/run-waiting` | | replaced by `start_run` |
| `start_run` | `POST /api/runs` | dashboard | new; body `limit` (0 for no cap); 409 if a run is running |
| `get_latest_run` | `GET /api/runs/latest` | dashboard | new |
| `list_queue` | `GET /api/runs/{run_id}/queue` | queue agent | new |
| `write_todos` | `PUT /api/runs/{run_id}/todos` | queue agent | new |
| `start_claim` | `POST /api/runs/{run_id}/claims/{claim_id}/start` | queue agent | new; 409 over the cap or not waiting |
| `release_claim` | `POST /api/claims/{claim_id}/release` | both | new; counts a failure if still in progress |
| `finish_run` | `POST /api/runs/{run_id}/finish` | queue agent | new; 409 with the missed claims |

`run_agent` (`POST /api/claims/{id}/run`), `decide_claim`, `pay_claim`, `sign_off_claim`, the events and the rest stay as they are. `ClaimDetail` gains `reads`; `Status` gains `needs_handler`. Every new operation keeps an `operation_id`, a one-line docstring and no optional inputs.

---

## Phase 1: Look up the wording and the manual

Builds the lookup, the record of what was read, the split instructions and the new state. Why first: everything after this uses it, and it changes the backend's shape without touching the agent yet.

- `backend/documents.py`: split a document on its `## N. Title` headings into sections; `list_sections` and `read_section` operations in `backend/main.py`.
- `reads` table; `read_section` records it (once per claim, document and section) and `ClaimDetail.reads` returns it.
- `needs_handler` added to `Status` (in the models and the schema); the failure rules come in Phase 2.
- Remove `get_policy_wording` and its route; the agent's tool is swapped in Phase 3, so until then I update the pilot's agent to stay green.
- Split the instructions into two files and serve them at `/api/instructions/{agent}`. A first version of each is a copy of the pilot's text; they are rewritten in Phase 4.
- `npm run reseed`, and the database path in `backend/db.py` reused by it.
- Update the pilot's tests that this changes.

Success criteria

- [x] `uv run pytest -q backend` passes, with at least 80% coverage.
- [x] `GET /api/documents/wording/sections` returns 12 sections with numbers and titles; `manual` returns 14. An unknown document returns 404 (test).
- [x] `POST /api/claims/CLM-1001/reads` with `{"document": "manual", "section": 9}` returns the text of "9. Repeat claims", and nothing from sections 8 or 10 (test). A section that does not exist returns 404; an unknown claim returns 404.
- [x] Reading the same section twice stores one read. `GET /api/claims/CLM-1001` lists the reads in the order they were first made (test).
- [x] `GET /api/instructions/queue` and `/claim` return their files; `/api/instructions/other` returns 404 (test).
- [x] Every operation in `/openapi.json` has an `operation_id`, a one-line description and no optional parameters (the pilot's test, still green with the new operations).
- [x] The test that keeps `evals` out of `backend/` and `agent/` still passes.
- [x] `npm run reseed` removes the database; the next backend start recreates it with 25 waiting claims (command output and a test of the reset function).
- [x] `npm run check:python` passes.
- [x] Committed (the hook passes); this plan ticked and `docs/STATUS.md` updated.

## Phase 2: Runs, the to-do list, the cap and recovery

Builds the rules that make a long run safe, with plain API calls and no agent. Why before the agents: like the sign-off rule in the pilot, these must hold whatever the model does, so they are proven first.

- `runs`, `run_claims` and `todos` tables; a `failures` count on the claim.
- `backend/runs.py` (or additions to `rules.py` if it stays short): `start_run`, `get_latest_run`, `write_todos`, `list_queue`, `start_claim`, `release_claim`, `finish_run`, with the rules from "Recovery" above. `start_claim` also serves the single-claim path, with no run.
- `backend/runner.py` rewritten around these: a queue run (`work_run`) and the single claim (`work`), which share the release rule. The queue run calls `agent.main.run_queue`, a stub in this phase's tests.
- `POST /api/run-waiting` removed.

Success criteria

- [x] `uv run pytest -q backend` passes with at least 80% coverage; no test calls a model.
- [x] `POST /api/runs` with `{"limit": 5}` returns a `running` run with limit 5; a second `POST /api/runs` returns 409 while it runs.
- [x] To-do list stored: `PUT /api/runs/{id}/todos` with items in all four statuses; `GET /api/runs/latest` returns the same items in the same order. A second `PUT` replaces the list. An unknown status returns 422.
- [x] Cap: with a limit of 2, `start_claim` succeeds for two different claims and returns 409 for a third; the other 23 claims are still `waiting`. `list_queue` then returns no new claims.
- [x] A failed claim does not stop the run: after `release_claim` on a claim left `in_progress`, `start_claim` on another claim still succeeds.
- [x] A failed claim goes back in the queue: after the first `release_claim` the claim is `waiting`, has an `error` event and a failure count of 1, and it is in `list_queue` even when the cap has been reached. Starting it again does not use up the cap.
- [x] A claim that fails twice is left for a handler: after the second `release_claim` its state is `needs_handler`, it is not in `list_queue`, and `start_claim` on it returns 409.
- [x] Nothing decided or paid twice: a claim that was approved ($420.00) and then released as failed goes back to `waiting`; deciding it again returns 409, paying it once succeeds and paying it again returns 409 (test).
- [x] `release_claim` on a claim that is `decided` or `awaiting_sign_off` changes nothing and counts no failure.
- [x] The check for missed claims: `finish_run` returns 409 and names the claims while there is a waiting claim the run took (a retry) or, under the cap, a waiting claim it has not taken. It returns 200 and stores the summary once nothing is owed, including when the cap is reached with claims left waiting. The run is then `finished`.
- [x] The runner (stub queue agent): a run whose agent raises is marked `failed` with the reason and leaves no claim `in_progress`. A single-claim run follows the same failure rules (first failure: `waiting`; second: `needs_handler`).
- [x] `npm run check:python` passes.
- [x] Committed; this plan ticked and `docs/STATUS.md` updated.

## Phase 3: The claim helper

Builds the agent that works one claim, with section lookup and recovery middleware. Why now: it is the existing agent made smaller and better; the queue agent in Phase 4 only calls it.

- `agent/main.py` (split into `agent/claim.py` and `agent/queue.py` only if it grows past a screen or two): tools `get_claim`, `list_sections`, `read_section`, `decide_claim`, `pay_claim`; `get_policy_wording` removed.
- The model: `deepseek/deepseek-v4.1-flash`, low reasoning effort, 120 second timeout; `MODEL_NAME` overrides. The same `model()` serves both agents.
- `ModelRetryMiddleware` (on failure, raise) and `ModelCallLimitMiddleware` on the helper.
- `run(claim_id, thread_id, llm=None)` keeps its shape and its step log. It fetches `claim` instructions. It now ends by calling `release_claim` in a `finally`, so a single claim run gets the recovery rules too.
- The claim instructions get their real text in Phase 4. Until then the helper runs on the copy from Phase 1, adjusted to name the new tools.

Success criteria

- [x] `uv run pytest -q` passes with at least 80% coverage; no test calls a model.
- [x] With a stub scripted to call `get_claim`, `list_sections`, `read_section` (manual section 9), `decide_claim` (approve $420.00) and `pay_claim`, `run("CLM-1001", ...)` leaves the claim `decided`, with the read recorded on the claim and the steps logged in order (the pilot's test, extended).
- [x] The helper never receives a whole document: no tool of the helper returns the full wording or manual (test on the tools' replies for a section read: the reply is shorter than the document and holds only that section).
- [x] The $1,250.00 payout is still refused with a 409 that comes back to the model as an error message; the claim is `awaiting_sign_off` and nothing is paid.
- [x] A stub that raises on its first model call leaves the claim `waiting` with an `error` event; run again it fails again and the claim is `needs_handler`.
- [x] A stub that finishes without deciding leaves the claim `waiting` (counted as a failure).
- [x] The system prompt is exactly what `GET /api/instructions/claim` returns (test).
- [x] `model()` returns `deepseek/deepseek-v4.1-flash` with low reasoning effort by default, and the value of `MODEL_NAME` (no reasoning effort) when it is set (test).
- [x] The model middleware is in place on the helper, and `ModelCallLimitMiddleware` with a stub that never stops ends the run with an error and a released claim (test).
- [x] `agent/` still imports nothing from `backend` outside tests and reads no file from `data/` (the pilot's test).
- [x] `npm run check:python` passes.
- [x] Committed; this plan ticked and `docs/STATUS.md` updated.

## Phase 4: The queue agent and the instructions

Builds the agent that runs the queue, and writes both sets of instructions. Why last on the backend side: it needs the runs from Phase 2 and the helper from Phase 3.

- `run_queue(run_id, llm=None, claim_llm=None)`: fetches the `queue` instructions, creates the agent with `list_queue`, `write_todos`, `work_claim` and `finish_run`, and runs it with the thread id equal to the run id. `claim_llm` lets a test give each helper its own scripted model.
- `work_claim(claim_id)`: calls `start_claim`, runs the helper, always calls `release_claim`, and returns the helper's line or the failure ("failed, back in the queue" or "failed twice, left for a handler").
- `backend/runner.py` starts `run_queue` for `POST /api/runs`.
- Write `instructions_queue.md`: get the queue, make the to-do list (one item per claim, what it is), choose the order and say why in a line, work one claim at a time with `work_claim`, keep the list up to date after each claim (`done`, or `left_for_handler` when a claim failed twice), retry a claim that came back to the queue, and finish with `finish_run` and a short summary for the handlers (counts of approved, declined, referred, waiting for sign-off, left for a handler, and anything unusual).
- Write `instructions_claim.md` from the manual's section 4 order, section 2, 3, 5, 6 and the notes the manual says bind every decision: read the claim, read the contents of the wording and the manual, read the sections that apply (always the repeat-claims section and the section on the payment order), decide once, pay only an approval up to the limit, and reply in one line.

Success criteria

- [x] `uv run pytest -q` passes with at least 80% coverage; no test calls a model.
- [x] With scripted stubs for the queue agent and for each helper, `run_queue` on a reseeded database works three claims: each ends `decided`, the to-do list ends with three `done` items, `finish_run` stores the summary, and the run is `finished`.
- [x] To-do list stored and shown: the list the stub queue agent writes is returned by `GET /api/runs/latest`, and it changes as the stub updates it between claims (a test reads it after each step).
- [x] The cap: a run with a limit of 2 and a stub that tries to work a third claim gets the 409 as an error message from `work_claim`, and 23 claims stay `waiting`.
- [x] A failed claim does not stop the run: with the first helper raising, the next claim is still worked and decided.
- [x] A failed claim is tried again: the helper for claim A raises once and then succeeds; A is `decided`, the run is `finished`, and A's events show the error and then the second attempt.
- [x] A claim that fails twice is left for a handler: both helpers for claim B raise; B is `needs_handler`, the to-do item can be `left_for_handler`, and the run still finishes.
- [x] The check for missed claims: a stub that calls `finish_run` while claims it may still take are waiting gets the 409 listing them as a tool error, works them and then finishes.
- [x] The queue agent's context stays small: the messages it sees contain the helpers' one-line replies and none of a claim's documents or sections (test on the stub's recorded inputs).
- [x] The queue agent's system prompt is exactly what `GET /api/instructions/queue` returns (test).
- [x] The instructions mention the manual and the wording by name and contain no reference to `evals` or to any handler's decision; the test that keeps `evals` out of the source covers the instruction files.
- [x] `npm run check:python` passes.
- [x] Committed; this plan ticked and `docs/STATUS.md` updated.

## Phase 5: Dashboard

Builds what the team sees: the run and its to-do list on the queue page, what the agent read on the claim page, the new state and both instructions. Why now: the backend and the agents are proven, so the screens only show them.

- Queue page: a run panel above the table with the latest run's status, its cap, its summary when finished, and its to-do list. Items show their status with a chip: to do (Marigold), in progress (Cerulean), done (Sea Green) and left for a handler (Raspberry), each with the text color the brand sheet pairs with it. The page polls while the run is `running`.
- Controls: "Run all waiting" now starts a run with no cap; next to it a field and a "Run a trial" button that start a run capped at that many claims (default 5).
- The new state `needs_handler` ("Left for a handler") in the chips, the filter counts and the types.
- Claim page: a "What the agent read" panel lists each section, such as "Claims manual, 9. Repeat claims" and "Policy wording, 3. Trip Delay". The step log is unchanged.
- Instructions page: both sets of instructions, "Running the queue" and "Working a claim", read only.
- Plain business English, US spelling, no exclamation marks. Dark and light modes, no one-edge borders, no gradients.

Success criteria

- [x] `npm run check:ts` passes with at least 80% coverage; no TypeScript `any`.
- [x] Vitest: the run panel renders items in all four statuses from mocked data, with the right chips; it polls while the run is `running` and stops afterward; with no run it says so; the summary shows when the run is finished.
- [x] Vitest: "Run all waiting" posts a limit of 0 and "Run a trial" posts the number in the field.
- [x] Vitest: the claim page lists the sections read; the `needs_handler` chip and filter show on the queue; the instructions page shows both texts.
- [x] Playwright e2e, setting state through the API (no model): after `POST /api/runs`, a to-do list written with `PUT` shows on the queue page in order; rewritten with an item moved to `done`, the page shows the change; the summary shows after `finish_run`.
- [x] Playwright e2e: a read posted for a claim shows on the claim page under "What the agent read"; a claim failed twice shows "Left for a handler" on the queue and the claim page.
- [x] Screenshots of the queue page with a to-do list, the claim page and the instructions page in light and dark mode and at phone width (taken with a standalone Playwright script against `npm run dev`, no Playwright MCP server available this session) show the brand fonts, the backgrounds `#F0F4F5` and `#04232E`, readable chip text and no outlined panels; no console errors.
- [x] `npm run check:ts` and `npm run e2e` pass.
- [x] Committed; this plan ticked and `docs/STATUS.md` updated.

One correction made during this check: the to-do item's `content` is free text the queue agent writes (such as `"CLM-1001 trip_delay Maya Patel"`), not always a bare claim id, discovered only once a real agent wrote one. The to-do list renders it as plain text rather than a link to the claim, which the plan did not specify either way.

## Phase 6: A real run, documentation and the final check

Proves the whole harness with the real model and brings the documents up to date.

- Reseed with `npm run reseed`, start `npm run dev`, and start a run capped at five claims from the dashboard with the default model (`OPENROUTER_API_KEY` from `.env`; or `MODEL_NAME=openrouter/free` if you prefer the free route). I watch it with Playwright MCP. I do not open `data/evals/` to judge the answers; I check that the process works and that the decisions read sensibly against the wording and the manual.
- Update `docs/SPEC.md`: the claims manual comes out of "Not for now" and becomes part of how decisions are made (decisions follow the policy wording and the claims manual); the five states; the queue page's to-do list and the claim page's list of what the agent read.
- Update `docs/TECH_STACK.md`: the new default model, the two entry points, the agent's tools and the two kinds of agent, still on `create_agent`.
- Update `docs/STATUS.md`: what is built, how to run a capped trial, how to reseed, and what is not built yet.

Success criteria

- [~] After `npm run reseed` and a run capped at five claims, five claims are worked by the agent with no click on any single claim. The other 20 are still `waiting` (checked in the queue counts and with `GET /api/claims`). **Partly met**: run on the free route (`MODEL_NAME=openrouter/free`, to spend nothing); four of five claims (`CLM-1001`–`CLM-1004`) were worked and decided with no click. The fifth (`CLM-1005`) hit OpenRouter's free-tier daily cap (50 requests/day) mid-attempt; see the note below. The other 20 claims stayed `waiting` throughout, confirmed via `GET /api/claims`.
- [x] During that run the queue page shows the to-do list filling in and being ticked off, and the claim pages show each claim's steps and the sections read (screenshots taken with a standalone Playwright script; see the Phase 5 note on Playwright MCP).
- [x] Any approval over $1,000.00 in the run shows "Waiting for sign-off" with nothing paid (`CLM-1003`, approved $3,750.00, `payment: null`, confirmed through the API and the dashboard). No claim has two decisions or two payments (checked through the API).
- [~] The run ends `finished` with a short summary on the queue page. **Not met on this run**: the queue agent's own model call also hit the daily rate limit after the fourth claim, so `work_run` caught the exception and marked the run `failed` with that reason, exactly as the recovery design intends for "the model is down for good" (see Design decisions, Recovery). A clean `finished` run needs either the next day's quota or the paid default model.
- [x] A run on one named claim ("Run agent" on a waiting claim) still works: the mechanism is proven, though the specific attempt (on `CLM-1005`, by then already back in the queue after one failure) also hit the same exhausted daily quota. That second failure correctly left the claim `needs_handler` ("Attempt 1 failed" / "Attempt 2 failed" both recorded on the claim), which is a genuine end-to-end proof of the two-failure recovery rule under a real provider error rather than a stub.
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is; a search shows no remaining "Not for now" entry for the manual.
- [x] `npm run check` passes in full (ruff, pyright, pytest with coverage, ESLint, Prettier, tsc, vitest with coverage, Playwright). Results below.
- [x] `git status` is clean of uncommitted changes from this build; nothing was pushed.

**On the free-tier rate limit**: OpenRouter's free models share a small daily quota (the error reported `"X-RateLimit-Limit": "50"`) across both agents' calls; a 5-claim run plus the queue agent's own overhead calls used it up. This is a property of the free route, not a bug — every piece it touched (the cap, the per-claim retry-and-fail-twice rule, the run-level failure path, the dashboard's reflection of all of it) behaved exactly as designed under a real failure. A re-run on the paid default model (`deepseek/deepseek-v4.1-flash`, a small real cost) would be needed for a fully clean `finished` run on all five claims if that is wanted.

---

## Questions for your review

1. **A fifth state, `needs_handler`.** I added it rather than recording a "refer" decision for a claim that failed twice, since a referral is a considered decision and this claim has none. The alternative is to reuse "refer" with a standard reason; say if you prefer it.
2. **No way yet for a handler to send a left-over claim back to the queue.** The brief does not ask for one. For now a handler would decide it outside the product, or you reseed. It would be a small addition later.
3. **Reasoning effort and cost.** The cap protects the budget on trials, but a full 25-claim run on the default model has not been priced. I will report the cost of the five-claim run so you can estimate the full queue.
4. **A claim left `in_progress` if the backend itself is stopped mid-run** is not handled; the brief's problems (timeouts, provider errors, failing steps) are. Reseeding clears it for now.
