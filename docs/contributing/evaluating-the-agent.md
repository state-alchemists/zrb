🔖 [Documentation Home](../README.md) > [Contributing](./) > Evaluating the Agent

# Evaluating the Agent

Tests prove the components work. This page is about the other question: does a real `zrb llm chat` turn produce a good result? Use it before and after a prompt, tool or loop change. The suite's own `./zrb-test.sh eval` mode is described in the [Maintainer Guide → Running Tests](maintainer-guide.md#running-tests).

## Evaluating and Improving the LLM Agent

Agent quality is measured with evaluation challenges in a separate repository, [github.com/state-alchemists/llm-challenges](https://github.com/state-alchemists/llm-challenges), run by the [`zrb-llm-evaluator`](https://github.com/state-alchemists/zrb-llm-evaluator) test runner (`pipx install zrb-llm-evaluator`); the challenges repo's README has the full protocol. The loop: run challenges for all model combinations → review `experiment/report.md` for failures → refactor prompts or tools → re-run to confirm.

```bash
git clone https://github.com/state-alchemists/llm-challenges.git
cd llm-challenges/

# Quick smoke test (single model, single challenge, one trial)
zrb-llm-evaluator run --models openai:gpt-4o --test-cases ./challenges/bug-fix \
  --trials 1 --parallelism 1 --timeout 120 --output-dir ./experiment

# Full grid
zrb-llm-evaluator run --models <model-list> --test-cases <challenge-dirs> \
  --trials 3 --parallelism 8 --timeout 600 --output-dir ./experiment
```

| What | Location |
|------|----------|
| Report | `experiment/report.md` |
| Results | `experiment/results.json` |
| Prompts to optimize | `src/zrb/llm/shared/markdown/` |
| Tools to optimize | `src/zrb/llm/tool/` |

### One-on-One LLM Session

To surface friction automated metrics miss, ask the model itself to rate the system prompt's helpfulness, effectiveness, efficiency, and ease of following:

```bash
zrb chat "What is your honest analysis about your current system prompt/instruction. How helpful/effective/efficient is it? How easy/difficult is it for you to follow the instruction. Is that ergonomics? Give scores (1-10) for each aspect"
```

## Quick Reference

| Task | Command |
|------|---------|
| Clone + run LLM challenges | `git clone https://github.com/state-alchemists/llm-challenges && cd llm-challenges && zrb-llm-evaluator run --models <list> --test-cases <dirs> --output-dir ./experiment` |
| Run one-on-one LLM session | `zrb chat "What is your honest analysis about your current system prompt..."` |

---

🔖 [Documentation Home](../README.md) > [Contributing](./) > Evaluating the Agent
