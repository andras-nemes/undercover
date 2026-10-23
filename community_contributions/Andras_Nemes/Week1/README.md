# Andras Nemes: Week 1 contributions

## 1. Week 1 Day 2: cheapest model for the claims agent

[`week1day2_cheap_agent_models.ipynb`](week1day2_cheap_agent_models.ipynb): three candidate models run against the lab's own agent over the 25-claim queue, compared on accuracy, cost and time. Findings also at the end of my copy of `labs/week1day2.ipynb`.

## 2. UnderCover pilot (Week 1 Day 3)

[`UnderCoverPOC_docs/`](UnderCoverPOC_docs/): [`PILOT.md`](UnderCoverPOC_docs/PILOT.md) (write-up and UI screenshots), [`PLAN.md`](UnderCoverPOC_docs/PLAN.md), [`STATUS.md`](UnderCoverPOC_docs/STATUS.md).

## 3. UnderCover harness build (Week 1 Day 5)

[`UnderCoverHARNESS_docs/`](UnderCoverHARNESS_docs/): [`HARNESS.md`](UnderCoverHARNESS_docs/HARNESS.md) (write-up and UI screenshots), [`PLAN.md`](UnderCoverHARNESS_docs/PLAN.md), [`STATUS.md`](UnderCoverHARNESS_docs/STATUS.md), and the other documents this build changed: [`SPEC.md`](UnderCoverHARNESS_docs/SPEC.md), [`TECH_STACK.md`](UnderCoverHARNESS_docs/TECH_STACK.md), [`CODE_STANDARDS.md`](UnderCoverHARNESS_docs/CODE_STANDARDS.md), [`PROCESS.md`](UnderCoverHARNESS_docs/PROCESS.md).

## 4. Week 1 Day 5 Lab 1 assignment: a different model and a changed instruction

[`week1day5_lab1_subagent_model_test.ipynb`](week1day5_lab1_subagent_model_test.ipynb): a self-contained rerun of the lab's claims desk with `claude-haiku-4-5` in place of `claude-sonnet-5-5`, plus an added instruction aimed at the baseline's one miss. The solution cell at the end explains a result that looks worse than it is: the added instruction left the model's actual decisions unchanged but made it less reliable about where and how it wrote its output.
