🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Maintainer Guide

# Maintainer Guide

This guide is for developers who contribute to or maintain the Zrb project itself. It outlines the project's architecture, conventions, and release process.

## Publishing Zrb

To publish Zrb, you need a `Pypi` account and an API token.

-   **Pypi**: Register at [https://pypi.org/](https://pypi.org/)
-   **TestPypi**: Register at [https://test.pypi.org/](https://test.pypi.org/)

Configure poetry with your token:
```bash
poetry config pypi-token.pypi <your-api-token>
```

Then, run the publishing command:
```bash
source ./project.sh
docker login -U stalchmst
zrb publish all
```

## Inspecting Import Performance

To inspect import performance and decide if a module should be lazy-loaded:
```bash
pip install benchmark-imports
python -m benchmark_imports zrb
```

## Profiling Zrb

To diagnose performance issues, generate a profile and visualize it.

**1. Generate Profile:**
```bash
python -m cProfile -o .cprofile.prof -m zrb --help
```

**2. Visualize Profile:**
-   **`snakeviz` (interactive HTML):**
    ```bash
    pip install snakeviz
    snakeviz .cprofile.prof
    ```
-   **`flameprof` (terminal flame graph):**
    ```bash
    pip install flameprof
    flameprof .cprofile.prof > flamegraph.svg
    ```

## Testing Strategies
The test suite uses `pytest` fixtures and `unittest.mock.patch` (as decorators or context managers) to isolate components and ensure correctness. Refer to existing tests in the `test/` directory for examples.

## Evaluating and Improving the LLM Agent

To maintain and improve the quality of the Zrb LLM agent, the project uses a set of automated evaluation challenges located in the `llm-challenges/` directory. The goal is to ensure the agent can handle various software engineering tasks by iteratively improving its system prompts and tool definitions.

The full instructions for the evaluation protocol are in `llm-challenges/AGENTS.md`. The core process is as follows:

### 1. Execute Challenges
A Python runner script orchestrates the entire evaluation. It runs `zrb llm chat` for every combination of model and challenge, executes automated verification scripts, and generates a report.

```bash
# Navigate to the challenges directory
cd llm-challenges/

# Run a quick verification test
python runner.py --models openai:gpt-4o google-gla:gemini-1.5-pro --timeout 120 --verbose

# Run the full test suite (example)
python runner.py --timeout 3600 --parallelism 12 --verbose --models <model-list>
```

### 2. Analyze the Report
The runner generates a detailed `REPORT.md` and `results.json` in the `llm-challenges/experiment/` directory. Review this report to identify any failures (marked with ⚠️ or ❌).

### 3. Optimize and Fix
If a challenge fails, analyze the detailed logs linked in the report to find the root cause. Then, refactor the core framework files:
*   **Prompts**: Modify files in `src/zrb/llm/prompt/markdown/`.
*   **Tools**: Modify tool definitions in `src/zrb/llm/tool/`.

After applying a fix, run the challenges again to verify the improvement.

---
This iterative process ensures that the agent's capabilities are continuously tested and enhanced in a systematic way.

