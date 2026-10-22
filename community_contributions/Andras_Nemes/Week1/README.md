# Andras Nemes: Week 1 contributions

This folder holds my work for Week 1. There are two pieces.

## 1. Week 1 Day 2 assignment: the cheapest model for the claims agent

The assignment is the "Your assignment" cell near the end of `labs/week1day2.ipynb`: with a goal of at least 15 / 25 correct consistently, using the agent, what is the cheapest model you can find?

**Solution:** [`week1day2_cheap_agent_models.ipynb`](week1day2_cheap_agent_models.ipynb), the only notebook in this folder.

It plugs three candidates into the lab's own agent (same tools, same system prompt, only the model changes) and runs each over the whole 25-claim queue:

| Model | Right / 25 | Cost (queue) | Time (queue) |
|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` (low) | 16 | $0.0097 | 206s |
| `qwen/qwen3.7-flash` (low) | 18 | $0.0275 | 1374s |
| `inclusionai/ling-3.0-flash` | 16 | $0.0061 | 389s |

The lab's Luna agent run is the baseline: 17 / 25 for $0.0087 in 203s. Ling-3.0 Flash was the cheapest of the three I tested. These are single runs, not repeated, so they do not yet show the "consistently" part of the challenge. The notebook ends with a summary table and findings. The same summary is also at the end of my copy of `labs/week1day2.ipynb`.

## 2. UnderCover pilot (Week 1 Day 3)

The documents for the pilot build are in [`UnderCoverPOC_docs/`](UnderCoverPOC_docs/):

- [`PILOT.md`](UnderCoverPOC_docs/PILOT.md): what I did and my takeaways. **It includes screenshots of the pilot's UI in action**: the queue, the agent working on a claim, a decision with its reasons, an approval waiting for a handler's sign-off, the agent's instructions, and dark mode. The image files are in [`UnderCoverPOC_docs/images/`](UnderCoverPOC_docs/images/).
- [`PLAN.md`](UnderCoverPOC_docs/PLAN.md): the plan for the pilot, with every success criterion ticked.
- [`STATUS.md`](UnderCoverPOC_docs/STATUS.md): what is built and how to run it.

The pilot code itself is in `backend/`, `agent/`, `dashboard/` and `e2e/` at the root of the repo.
