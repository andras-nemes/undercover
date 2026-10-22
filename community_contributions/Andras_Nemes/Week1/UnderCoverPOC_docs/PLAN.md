# Plan: the claims pilot

Source: `docs/SPEC.md`, built to `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`. Starting point: the hello-world skeleton in `docs/STATUS.md`.

## What we are building

1. A backend (FastAPI and SQLite) that holds the claims queue and enforces the rules: the $1,000 sign-off, and one decision and one payment per claim.
2. The UnderCover Agent, which reads a claim, decides it, and pays it when it may. It touches claims and its own instructions only through the backend's API.
3. A dashboard for the handlers: the queue and each claim's state, the full claim with the agent's decision and reasons, the agent's steps while it works, and the agent's instructions read only.

Out of scope, per the spec: the claims manual, sign-in, real payments, messages to customers. Out of scope for today: anything from a later day's brief (tools, middleware, durable state, evals scoring).

## Design decisions

These are the choices I made where the spec is silent. Please check them in your review.

- **Claim states.** `waiting` (no decision, not running), `in_progress` (the agent is running), `awaiting_sign_off` (approved over $1,000, not yet signed off), `decided`. A decline or a referral is `decided` as soon as the agent records it. An approval is `decided` once it is paid.
- **The sign-off rule lives in the backend, in the pay operation.** `pay_claim` refuses with a 409 if the claim has no approval, if the amount is not the approved payout, if the claim was already paid, or if the amount is over the limit and no handler has signed off. The limit is read from `data/company.json` (`payout_approval_limit`), not hard-coded. Over means strictly more than $1,000.00.
- **Signing off releases the payment.** `sign_off_claim` records which handler signed and then pays the approved amount through the same code path as `pay_claim`. This means a handler clicks once. The agent cannot pay a claim over the limit before that, however it tries.
- **Handlers without sign-in.** The spec says no sign-in, so the dashboard asks the handler to pick their name from `handlers.json` when signing off. The backend checks `can_approve_over_limit`.
- **The agent's instructions are stored in the backend** (`backend/instructions.md`) and served at `GET /api/instructions`. The agent fetches them at the start of each run and uses them as its system prompt, and the dashboard shows the same text. One source, so what the handlers read is what the agent follows.
- **What the agent sees about a customer.** The claim, the policy with its plan limits, and the customer's name and claim history. Not their address, phone number or date of birth, since the decision does not need them.
- **The agent never sees `data/evals/`.** The backend seeds only from the other files in `data/`, and a test fails if `backend/` or `agent/` mention the evals folder. I will not open `data/evals/` during the build.
- **How the agent is started.** From the dashboard: a "Run agent" button on a waiting claim, and "Run all waiting", which works the claims one at a time. The backend starts the agent in a background task and the dashboard polls for progress. The backend's runner imports `agent.main.run`; the agent still reaches claims only through HTTP.
- **Steps while it works.** `agent.main.run` streams the agent's updates and posts each one to the backend as an event (started, tool call, tool result, finished, error). The dashboard shows the events as a timeline.
- **A failed run** records an `error` event and puts the claim back to `waiting`, so a crash never leaves a claim stuck in progress. This is the one place I catch an exception.
- **API shape.** Every operation has an `operation_id`, a one-line docstring and no optional inputs. Filtering the queue happens in the dashboard. `decide_claim` takes `decision`, `payout` (0 unless approving), `reason` and `policy_section`, all required.
- **Money** is stored as dollars rounded to two decimals and shown as `$1,250.00`.
- **No new dependencies.** `sqlite3` from the standard library, a small hash-based router in the dashboard, plain CSS with the brand colors as variables.
- **Tests never call a model.** They use the stub model pattern already in `agent/tests/test_agent.py`.
- **Resetting.** The database is `backend/undercover.db`, created and seeded on first start and ignored by git. Delete the file to start the queue again.

### Backend API

| operation_id | Route | Used by |
|---|---|---|
| `health` | `GET /api/health` | exists |
| `list_claims` | `GET /api/claims` | dashboard |
| `get_claim` | `GET /api/claims/{claim_id}` | dashboard, agent |
| `get_policy_wording` | `GET /api/policy-wording` | agent |
| `get_instructions` | `GET /api/instructions` | dashboard, agent |
| `list_handlers` | `GET /api/handlers` | dashboard |
| `list_events` | `GET /api/claims/{claim_id}/events` | dashboard |
| `add_event` | `POST /api/claims/{claim_id}/events` | agent |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` | agent |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | agent |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | dashboard |
| `run_agent` | `POST /api/claims/{claim_id}/run` | dashboard |
| `run_waiting_claims` | `POST /api/run-waiting` | dashboard |

### Agent tools

`get_claim(claim_id)`, `get_policy_wording()`, `decide_claim(...)` and `pay_claim(claim_id, amount)`, each a thin call to the matching route. The existing `check_backend` hello-world tool is removed. The model stays `openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME` if set.

---

## Phase 1: Backend foundation and read API

Builds the database, seeds it from `data/`, and serves everything the dashboard and agent need to read. Why first: every later phase stands on real claims.

- `backend/db.py`: SQLite connection, schema, seeding on first start. Path from env `UNDERCOVER_DB`, default `backend/undercover.db`. Tables for claims, policies, customers, plans, handlers, settings, decisions, payments, sign-offs and events.
- `backend/instructions.md`: the first version of the agent's instructions (see Phase 3 for what it covers).
- `backend/main.py`: the read operations, with Pydantic response models.
- `.gitignore`: add the database file.

Success criteria

- [x] `uv run pytest -q backend` passes; backend coverage is at least 80%.
- [x] After a first start on an empty path, the database holds 25 claims all `waiting`, 50 policies, 49 customers, 3 handlers, 3 plans, and the $1,000 limit from `company.json`. A second start does not duplicate rows (test).
- [x] `GET /api/claims` returns 25 summaries, each with `claim_id`, `claim_type`, `summary`, `customer_name`, `amount_claimed`, `status`, `decision` and `payout`.
- [x] `GET /api/claims/CLM-1001` returns the claim with its items and documents, the policy with the plan's limits, and the customer's name and previous claims. The response contains no address, phone or date of birth (test).
- [x] `GET /api/claims/CLM-9999` returns 404.
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`; `GET /api/instructions` returns `backend/instructions.md`; `GET /api/handlers` returns the 3 handlers.
- [x] Every operation in `/openapi.json` has an `operation_id` and a one-line description, and no optional parameters (test that walks the schema).
- [x] A test fails if any source file in `backend/` or `agent/` mentions `evals`, so the seeding code cannot read the answer key.
- [x] `npm run check:python` passes.
- [x] Committed (the hook passes); `docs/PLAN.md` ticked and `docs/STATUS.md` updated.

## Phase 2: Decisions, payments and the sign-off rule

Builds the write side and the rules. Why before the agent: the rules must hold whatever the agent does, so they are built and proven first, with plain API calls.

- `decide_claim`: one decision per claim; approve needs a payout above 0; decline and refer need a payout of 0.
- `pay_claim` and `sign_off_claim` as described under Design decisions.
- `add_event` and `list_events`.
- Status changes in one small module, so the four states are defined in one place.

Success criteria

- [x] `uv run pytest -q backend` passes with at least 80% coverage.
- [x] Decide CLM-1001 as an approval of $420.00, then pay $420.00: both return 200, and `GET /api/claims/CLM-1001` shows status `decided`.
- [x] Decide a claim as an approval of $1,250.00: its status is `awaiting_sign_off`. `POST payment` with $1,250.00 returns 409, the claim stays `awaiting_sign_off` and no payment row exists (test, this is the spec's key rule).
- [x] Approval of exactly $1,000.00 can be paid with no sign-off; $1,000.01 cannot.
- [x] `POST sign-off` with a valid handler on that claim returns 200, records the handler and one payment of $1,250.00, and the status becomes `decided`. A second sign-off or a second payment returns 409.
- [x] `POST sign-off` on a claim that is not awaiting sign-off returns 409; with an unknown handler returns 404.
- [x] Paying a claim with no decision, a declined or a referred claim returns 409; paying an amount different from the approved payout returns 409.
- [x] A second decision on the same claim returns 409; an approval with payout 0, or a decline with a payout above 0, returns 422.
- [x] A decline and a referral each become `decided` immediately and cannot be paid.
- [x] Events are returned in the order they were added, each with `kind`, `text` and a timestamp.
- [x] `npm run check:python` passes.
- [x] Committed; `docs/PLAN.md` ticked and `docs/STATUS.md` updated.

## Phase 3: The UnderCover Agent and the runner

Replaces the hello-world agent with the claims agent, and lets the backend start it. Why now: the API and rules are proven, so the agent only has to use them.

- `agent/main.py`: the four tools; `run(claim_id, thread_id, llm=None)` fetches the instructions from the backend, runs the agent with `stream_mode="updates"`, posts an event for each step, and returns the final reply.
- `backend/instructions.md`: the first full version. It tells the agent to read the claim, read the policy wording, decide by the wording alone, work out the payout using the wording's section 10 (eligible amount, minus other payments, minus the deductible, capped at the benefit maximum), explain in two or three sentences with the section it relied on, and pay only if it approved. It says a claim is referred when it needs someone's judgment or more information, and that it must say what is missing. It does not mention the claims manual.
- `backend/runner.py`: `run_agent` and `run_waiting_claims` as background tasks that set `in_progress`, call `agent.main.run`, and on an exception record an `error` event and reset the claim to `waiting`.
- The agent's HTTP client points at a configurable backend URL (default `http://localhost:8000`) so tests can route it to the app.

Success criteria

- [x] `uv run pytest -q` passes with at least 80% coverage; no test calls a model.
- [x] With a stub model scripted to call `get_claim`, `get_policy_wording`, `decide_claim` (approve $420.00) and `pay_claim`, `run("CLM-1001", ...)` leaves the claim `decided`, with the decision, reason and policy section stored.
- [x] With a stub that approves $1,250.00 and then tries `pay_claim`, the tool returns the 409 as an error message to the model, the claim is `awaiting_sign_off` and nothing was paid.
- [x] The run posts events in order: started, one tool call and one tool result per tool, finished. `GET /api/claims/{id}/events` shows them.
- [x] The system prompt used by the agent is exactly what `GET /api/instructions` returns (test).
- [x] `POST /api/claims/CLM-1001/run` with a stub agent returns immediately with status `in_progress`; after the background task finishes the claim has a decision. Running a claim that is not `waiting` returns 409.
- [x] A stub agent that raises leaves the claim `waiting` with an `error` event.
- [x] `POST /api/run-waiting` with a stub agent decides every waiting claim, one at a time.
- [x] `agent/` contains no import of `backend` outside of tests, and no tool reads a file from `data/` (test or grep).
- [x] `npm run check:python` passes.
- [x] Committed; `docs/PLAN.md` ticked and `docs/STATUS.md` updated.

## Phase 4: Dashboard, the queue and the instructions

Builds the app shell, the brand and the first two views. Why before the claim page: the claim page links from the queue.

- Brand: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts; colors as CSS variables; light and dark through `prefers-color-scheme`; panels rounded with no outline; no one-edge borders, no thin lines across the top, no gradient fills.
- State chips: waiting in Marigold, in progress in Cerulean, waiting for sign-off in Coral, decided in Sea Green, each with the text color the brand sheet pairs with it.
- A small hash router: `#/` the queue, `#/claims/CLM-1001` a claim, `#/instructions`.
- `dashboard/src/api.ts`: strict types for every response and one `fetch` helper; no `any`.
- Queue page: all claims with id, type, customer, amount claimed, state chip, and the decision and payout once there is one; counts per state at the top with a filter.
- Instructions page: the agent's instructions, read only.
- Replaces the hello-world "Backend: up" page, so `e2e/health.spec.ts` is replaced by `e2e/queue.spec.ts`.
- `playwright.config.ts`: the test backend runs on port 8001 with a fresh temporary database, and Vite on port 5174 proxying to it (the proxy target comes from an environment variable), so end-to-end tests never touch the development database and never reuse a dev server.

Success criteria

- [x] `npm run check:ts` passes: Prettier, ESLint, `tsc` in strict mode, and vitest with at least 80% coverage.
- [x] Vitest: the queue renders rows and state chips from a mocked `fetch`; the filter narrows the rows; the instructions page renders the text; the router picks the right view.
- [x] `grep -rn "any" dashboard/src` finds no TypeScript `any` type.
- [x] Playwright e2e: the queue shows 25 claims, all in the "Waiting" state; the instructions page shows the text from `GET /api/instructions`.
- [x] Playwright MCP, `npm run dev` running: screenshots of the queue and the instructions page in light and dark mode show the brand fonts, the page backgrounds `#F0F4F5` and `#04232E`, readable chip text, and no outlined panels.
- [x] Browser console shows no errors on either page.
- [x] `npm run check:ts` and `npm run e2e` pass.
- [x] Committed; `docs/PLAN.md` ticked and `docs/STATUS.md` updated.

## Phase 5: Dashboard, the claim page

Builds the page that makes the pilot usable: the full claim, the decision, the live steps, running the agent and signing off.

- Claim page: the customer's story, the items claimed, each document as text, the policy (plan, add-ons, trip dates, travelers), and the customer's earlier claims.
- Decision panel: the outcome, the payout in dollars, the reason and the policy section.
- Steps panel: the events as a timeline, refreshed every two seconds while the claim is `in_progress`.
- Actions: "Run agent" on a waiting claim; on a claim waiting for sign-off, a handler picker and a "Sign off and pay" button; "Run all waiting" on the queue page.
- Plain business English, US spelling, no exclamation marks.

Success criteria

- [x] `npm run check:ts` passes with at least 80% coverage.
- [x] Vitest: the claim page renders each section from mocked data; the steps panel polls while in progress and stops afterward; "Run agent" posts to the right route; the sign-off button posts the chosen handler; the sign-off controls appear only in `awaiting_sign_off`.
- [x] Playwright e2e, setting state through the API with the test request fixture (no model): a claim approved at $420.00 and paid shows the state "Decided", the payout `$420.00`, the reason and the policy section.
- [x] Playwright e2e: a claim approved at $1,250.00 shows "Waiting for sign-off"; the payment attempt through the API returns 409 and the page still says "Waiting for sign-off"; choosing a handler and clicking "Sign off and pay" changes the page to "Decided" with the handler's name and `$1,250.00`.
- [x] Playwright e2e: events posted through the API appear on the claim page in order.
- [x] Playwright MCP against `npm run dev`: open `CLM-1001`, check the layout in light and dark mode at desktop and phone width, and that the console is clean.
- [x] `npm run check:ts` and `npm run e2e` pass.
- [x] Committed; `docs/PLAN.md` ticked and `docs/STATUS.md` updated.

## Phase 6: A real run, documentation and the final check

Proves the whole chain with a real model, then tidies the documentation.

- One live run of the agent on a few claims through the dashboard, using `OPENROUTER_API_KEY` from `.env` (or `MODEL_NAME=openrouter/free` if the student prefers the free route). I will not look at `data/evals/` to judge the answers; the spec keeps scoring for later. I check that the process works and that the decisions read sensibly against the policy wording.
- `README.md` in the repo root is left as it is; the product's short run instructions go in `docs/STATUS.md`: what is built, how to run it (`npm run dev`), how to reset the queue.
- Update `docs/STATUS.md` to describe the finished pilot.

Success criteria

- [x] With the key in `.env` and `npm run dev` running, click "Run agent" on three claims of different types in the dashboard, using Playwright MCP: each moves from Waiting to In progress to a final state, the steps appear while it works, and each has a decision, reasons and a policy section.
- [x] If the agent approves any claim over $1,000.00 in these runs, it shows "Waiting for sign-off" with nothing paid until a handler signs off in the dashboard.
- [x] `docs/STATUS.md` lists what is built, how to run it, how to reset the queue, and what is not built yet.
- [x] `npm run check` passes in full (ruff, pyright, pytest with coverage, ESLint, Prettier, tsc, vitest with coverage, Playwright). I will report the results.
- [x] `git status` is clean of uncommitted changes from this build; nothing was pushed.

---

## Questions for your review

1. **Sign-off releases the payment automatically.** The alternative is that sign-off only records the handler and a second step pays. One click seemed right for handlers; say if you want two steps.
2. **No reject on sign-off.** The spec only mentions signing off, so a handler cannot send an over-limit approval back in this pilot. Adding that later would be a small change.
3. **Running the agent from the dashboard** rather than from a command line. I chose it because the spec wants handlers to watch the agent work. Say if you would rather run it from the terminal.
