# Status

The pilot is being built in phases (see `docs/PLAN.md`).

## Built

- `backend/`: FastAPI and SQLite. On first start it creates `backend/undercover.db` and seeds it from `data/` (never `data/evals/`). Read operations: `list_claims`, `get_claim`, `get_policy_wording`, `get_instructions`, `list_handlers`. Customers keep only a name and a claim history.
- The rules, in `backend/rules.py`: one decision per claim (`decide_claim`), `pay_claim`, `sign_off_claim` and the agent's step log (`add_event`, `list_events`). A claim is `waiting`, `in_progress`, `awaiting_sign_off` or `decided`. A payout over $1,000.00 (the limit in `data/company.json`) is refused with a 409 until a handler signs off; signing off releases the payment.
- `backend/instructions.md`: the agent's instructions, served at `GET /api/instructions`.
- `agent/`: the UnderCover Agent. `run(claim_id, thread_id)` fetches its instructions from the backend, works the claim with four tools (`get_claim`, `get_policy_wording`, `decide_claim`, `pay_claim`, each a call to the backend API) and posts each step to the claim's event log. It reaches nothing but the API. The backend address is `BACKEND_URL` (default `http://localhost:8000`).
- `backend/runner.py`: `POST /api/claims/{id}/run` and `POST /api/run-waiting` start the agent in a background task. A failed run records an `error` event and puts the claim back to `waiting`.
- `dashboard/`: React, Vite and TypeScript, in the UnderCover brand with light and dark modes. The queue (`#/`) with a count and a filter per state, and the agent's instructions, read only (`#/instructions`). The claim page (`#/claims/<id>`): the story, items, documents, policy and the customer's history, the agent's decision with its reason and policy section, the agent's steps (refreshed every two seconds while it works), a "Run agent" button on a waiting claim, and a handler picker with "Sign off and pay" on a claim waiting for sign-off. The queue has "Run all waiting". A small hash router, no extra dependencies.
- `e2e/`: Playwright tests run against their own backend (port 8001, a fresh temporary database) and their own dashboard (port 5174), one worker, files in order (`01-queue.spec.ts` first, while every claim is still waiting). `02-claim.spec.ts` plays the agent's part through the API, since tests never call a model.

## Run it

`uv sync` and `npm install`, then `npm run dev` (backend on port 8000, dashboard on 5173). Delete `backend/undercover.db` to reset the queue. `npm run check` runs every check.
