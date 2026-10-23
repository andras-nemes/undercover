# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: two agents, both built with LangChain's `create_agent` on OpenRouter. `agent/harness.py` holds the model, the middleware (`ModelRetryMiddleware`, `ModelCallLimitMiddleware`) and the run loop, and knows nothing about claims. `agent/tools.py` holds every tool for both agents, reached through `ToolRuntime[ClaimContext]` and `ToolRuntime[QueueContext]`. `agent/api.py` is the one module that calls the backend; nothing else in `agent/` does. Two entry points in `agent/main.py`: `run(claim_id, thread_id)`, the claim helper (`get_claim`, `list_sections`, `read_section`, `decide_claim`, `pay_claim`), and `run_queue(run_id)`, the queue agent (`list_queue`, `write_todos`, `work_claim`, `finish_run`), which hands each claim to a fresh helper. It uses `deepseek/deepseek-v4.1-flash` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
