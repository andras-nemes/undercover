# Status

The pilot is built (see `docs/PLAN.md`) and the harness build (see `docs/PLAN_HARNESS.md`) is done: a backend that holds the claims queue and enforces the rules, a queue agent that works the whole queue through claim helpers, and a dashboard that shows the run, its to-do list and what each agent read.

## Built

- `backend/`: FastAPI and SQLite. On first start it creates `backend/undercover.db` and seeds it from `data/` (never `data/evals/`). Read operations: `list_claims`, `get_claim`, `list_sections`, `get_instructions`, `list_handlers`. Customers keep only a name and a claim history.
- The rules, in `backend/rules.py`: one decision per claim (`decide_claim`), `pay_claim`, `sign_off_claim` and the agent's step log (`add_event`, `list_events`). A claim is `waiting`, `in_progress`, `awaiting_sign_off`, `decided` or `needs_handler` (left for a handler after two failed attempts). A payout over $1,000.00 (the limit in `data/company.json`) is refused with a 409 until a handler signs off; signing off releases the payment.
- `backend/documents.py`: splits the policy wording and the claims manual into numbered sections (`## N. Title` headings), served one at a time by `GET /api/documents/{document}/sections` and `POST /api/claims/{id}/reads`. Every read is recorded on the claim (`reads` in the claim detail); the agent never receives a whole document.
- `backend/runs.py`: runs, the to-do list, the cap and recovery. `POST /api/runs` (body `limit`, 0 for no cap) starts a run; `GET /api/runs/latest` returns it with its to-do list. The cap and the closing check (`finish_run` refused with a 409 naming any claim the run still owes) are enforced by the backend, not trusted to the model. `release_claim` settles a claim after an agent has worked on it: one still in progress goes back to `waiting` the first time and to `needs_handler` the second.
- `backend/instructions_queue.md` and `backend/instructions_claim.md`: each agent's instructions, goal-oriented rather than step-by-step scripts, served at `GET /api/instructions/{agent}`.
- `agent/`: the UnderCover Agent, split so the harness (the model, the middleware and the loop) knows nothing about claims.
  - `agent/api.py`: every call to the backend, in one place, through `BACKEND_URL` (default `http://localhost:8000`). No other module in `agent/` calls the backend directly.
  - `agent/harness.py`: builds a `create_agent` with `ModelRetryMiddleware` (back off and retry) and `ModelCallLimitMiddleware` (a run that loops forever fails instead of burning tokens), and runs it, reporting each step.
  - `agent/tools.py`: every tool, for both agents, using `ToolRuntime[ClaimContext]` and `ToolRuntime[QueueContext]` to reach the claim or run they are scoped to.
  - `agent/main.py`: two entry points. `run(claim_id, thread_id)` is the claim helper: a fresh agent per attempt with `get_claim`, `list_sections`, `read_section`, `decide_claim` and `pay_claim`. `run_queue(run_id)` is the queue agent: `list_queue`, `write_todos`, `work_claim` (hands a claim to a fresh helper and reports back in one line) and `finish_run`. Both post their steps to the claim's event log and reach nothing but `agent/api.py`.
  - `deepseek/deepseek-v4.1-flash` at low reasoning effort is the default model for both agents (`MODEL_NAME` overrides it); a 120-second timeout so a stuck call fails and gets retried.
- `backend/runner.py`: `POST /api/claims/{id}/run` starts the claim helper on one claim and `POST /api/runs` starts the queue agent, both in a background task, each releasing the claim or failing the run if the agent stops without finishing.
- `dashboard/`: React, Vite and TypeScript, in the UnderCover brand with light and dark modes. The queue (`#/`) has a run panel above the table: the latest run's status, its cap, its summary when finished, and its to-do list with a chip per item (to do, in progress, done, left for a handler); "Run all waiting" starts an uncapped run and a "Run a trial" field (default 5) starts a capped one. A count and a filter per state, including "Left for a handler". The agent's instructions, both sets, read only (`#/instructions`). The claim page (`#/claims/<id>`): the story, items, documents, policy and the customer's history, the agent's decision with its reason and policy section, the agent's steps (refreshed every two seconds while it works), a "What the agent read" panel listing each section by document and title, a "Run agent" button on a waiting claim, and a handler picker with "Sign off and pay" on a claim waiting for sign-off. A small hash router, no extra dependencies.
- `e2e/`: Playwright tests run against their own backend (port 8001, a fresh temporary database) and their own dashboard (port 5174), one worker, files in order (`01-queue.spec.ts` first, while every claim is still waiting). `02-claim.spec.ts` plays the agent's part through the API, since tests never call a model.

## Run it

`uv sync` and `npm install`, then `npm run dev` (backend on port 8000, dashboard on 5173). `npm run reseed` deletes `backend/undercover.db`; the next start rebuilds and reseeds it (needed once, since the harness build changed the schema). `npm run check` runs every check.

## How a claim moves

1. Open a waiting claim in the dashboard and click "Run agent", or start a run from the queue page: "Run all waiting" for no cap, or "Run a trial" for a capped number of claims. The agent needs `OPENROUTER_API_KEY` in `.env`; set `MODEL_NAME` (for example `openrouter/free`) to use another model.
2. A queue run lists the waiting claims, hands each to a fresh claim helper in turn, and keeps a to-do list as it goes. The helper reads the claim and the sections of the wording and the manual it needs, records its decision and, if it approved $1,000.00 or less, pays it.
3. An approval over $1,000.00 waits for sign-off. The backend refuses the payment, even if the agent tries to pay. A handler picks their name on the claim page and clicks "Sign off and pay".
4. A claim a helper leaves unfinished (a model error, a timeout, or the call-limit cap) goes back to `waiting` for a retry; a claim that fails twice is left for a handler (`needs_handler`).

The pilot's live run (before the harness build) worked three claims end to end: a trip delay approved and paid, a baggage delay approved and paid, and an emergency medical approval of $3,750.00 that the agent tried to pay, was refused with a 409, and left waiting until a handler signed off in the dashboard.

The harness build's live run (`docs/PLAN_HARNESS.md` Phase 6), capped at five claims on the free model route (`MODEL_NAME=openrouter/free`, to spend nothing): four claims were worked with no click on any single claim, namely a trip delay, a baggage claim and a baggage delay approved and paid, and an emergency medical claim approved at $3,750.00 and correctly left waiting for sign-off. The fifth claim and the queue agent's own next step then hit OpenRouter's free-tier daily cap (50 requests/day, shared by both agents); the run ended `failed` with that reason, and the fifth claim, retried once more by hand, failed a second time for the same reason and was correctly left for a handler. Every rule this run could exercise held under a real provider failure, not a stub: the sign-off limit, no double decision or payment, the cap, the retry-once-then-leave-for-a-handler rule, and the run failing cleanly when the model is down for good. A run on the paid default model would be needed to see a `finished` run with a summary.

## Not built

Sign-in, real payments, messages to customers, and any scoring of the agent against the handlers' decisions (`data/evals/` has not been opened).

## Harness build (`docs/PLAN_HARNESS.md`)

All six phases are done and committed: the document lookup and reads, the runs/to-do list/cap/recovery rules, the claim helper, the queue agent with both sets of instructions, the dashboard, and the live run above.

A review of the agent code after Phase 4 (`docs/HUMAN_REVIEW_HARNESS.md`) found hardcoded backend URLs in more than one place, no single module for backend calls, the harness mixed with claims domain logic, and over-prescriptive instructions. The agent was restructured in response: `agent/api.py` is now the one place that calls the backend, `agent/harness.py` holds the model/middleware/loop and knows nothing about claims, `agent/tools.py` holds every tool using `ToolRuntime`, and both instruction files were rewritten to state a goal rather than a fixed script. See `docs/CODE_STANDARDS.md` for the standards added to keep this from recurring.
