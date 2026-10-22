# UnderCover pilot

## What I did

I built the Week 1 Day 3 pilot for UnderCover Travel Insurance with Claude Code, working from the course documents in `docs/`. I acted as the forward deployed engineer: I asked for a plan, reviewed it, then asked for the build.

**The plan.** Claude Code read `SPEC.md`, `TECH_STACK.md`, `CODE_STANDARDS.md`, `PROCESS.md`, `BRAND.md` and `STATUS.md`, then wrote `PLAN.md` without writing any code. The plan has six phases, each with checkbox success criteria that can be verified: tests that pass, API calls with their expected status codes, and pages checked in a browser with the Playwright MCP server. It also listed the choices the spec left open, for me to review before the build started.

**The build.** Claude Code implemented the six phases in order. After each one it checked every criterion, ticked it off in `PLAN.md`, updated `STATUS.md` and committed. The pre-commit hook ran the checks on every commit, and nothing was committed with `--no-verify`.

1. **Backend foundation.** FastAPI and SQLite, seeded from `data/`. Read operations for claims, policy wording, instructions and handlers. Customers keep only a name and a claim history.
2. **Rules.** One decision per claim, payments, and sign-off. A payout over $1,000.00 is refused with a 409 until a handler signs off, and signing off releases the payment.
3. **The UnderCover Agent.** A LangChain agent with four tools that call the backend API. It fetches its instructions from the backend and posts each step to a log. The backend can start it in the background.
4. **Dashboard, queue and instructions.** React, Vite and TypeScript in the UnderCover brand, with light and dark modes.
5. **Dashboard, claim page.** The full claim, the decision with its reason and policy section, live agent steps, "Run agent", "Run all waiting" and sign-off.
6. **A live run and the final check.**

**Results.**

- `npm run check` passes in full: ruff, pyright, pytest (99% coverage), ESLint, Prettier, `tsc`, vitest (100% statement coverage) and 5 Playwright tests.
- No test calls a model. Python tests use a stub model, and the end-to-end tests play the agent's part through the same API.
- I ran the agent from the dashboard on three claims with the real model, `openai/gpt-6-luna`:
  - CLM-1001, a trip delay: approved $420.00 and paid.
  - CLM-1004, a baggage delay: approved $186.00 and paid.
  - CLM-1003, emergency medical: approved $3,750.00. The agent tried to pay, the backend refused, and the claim waited as "Waiting for sign-off". I then signed it off in the dashboard as a handler and it was paid.

**What I did not do.** I did not open `data/evals/`, so I have not scored the agent against the handlers' decisions. The agent ignores the claims manual, as the spec says for the pilot. There is no sign-in, no real payments and no messages to customers.

## My takeaways

### The way of working

It is amazing how well modern LLM tools like Claude and Codex can be used to build something relatively quickly. Projects, even small POCs like this one, would have taken a single developer days or even weeks. Now it takes a couple of hours.

Most of that time goes into writing documentation, guardrails and guidelines for the agent, and into asking the important questions. The new kind of developer is more like an architect: someone who does not necessarily write code anymore, but uses coding tools as a partner that needs input and guidance to build something new. The architect remains the one ultimately responsible.

I like this new way of working. In my current role I do not have the time to sit down and write code the way we did before LLMs; that is out of the question. With LLMs I suddenly feel empowered to build things again, which is something I had been missing. I like building, and I am fine doing it without hands-on coding.

### From this build

- **A plan with checkable criteria makes the build easier to review.** The plan was the point where I could change the design. Its open choices, such as signing off releasing the payment and the dashboard starting the agent, were cheap to discuss before any code existed. Because each criterion was a command or a page to check, "done" was a fact, not an opinion.
- **Enforce the rules in the system, not in the prompt.** The agent's instructions tell it not to pay over $1,000.00, but the real guarantee is that the backend refuses. In the live run the agent tried to pay anyway and was blocked. The instructions are a request, and the backend check is the guarantee.
- **Give the agent only an API.** The agent reaches claims and its own instructions only through the backend. That kept the held-out answer key out of its reach, and I could write a test that fails if the source mentions it. It also let me limit what personal data the agent sees: a customer's name and history, not their address, phone or date of birth.
- **Tests with a stub model catch more than I expected.** Because tests never call a model, they are fast and free. Most of the problems the checks found were in the dashboard's polling and timing, not in the agent. A separate live run is still needed to see how the real model behaves.
- **The live run shows the loop works, not that the agent is accurate.** Three claims behaving sensibly says nothing about accuracy across the queue. Scoring against `data/evals/` is the next job, and it is the real measure of whether the agent decides as well as our handlers do.
- **Constraints in `docs/` shape the code.** Strict lint rules, a coverage threshold and "no overly defensive code" pushed the build toward small functions and few try/catch blocks. The only place an exception is caught is the agent runner, where a crash would otherwise leave a claim stuck "in progress".
