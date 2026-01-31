# LLM Framework Evaluation & Optimization Protocol

**TARGET AUDIENCE:** AI Agents (Zrb, Gemini CLI, etc.) and Maintainers.
**OBJECTIVE:** Run, Evaluate, and Improve the `zrb` LLM framework.

## Mission
Your goal is to ensure `zrb llm chat` can autonomously and correctly solve complex software engineering tasks. You will run a series of challenges, evaluate the results against strict criteria, and modify the `zrb` source code (prompts and tool definitions) to fix any failures.

## The Challenges
Located in: `challenges/` (relative to this directory)
- `bug-fix`
- `copywriting`
- `feature`
- `refactor`
- `research`

## Execution Protocol

**Prerequisite:** Open a terminal in the `llm-challenges/` directory.

### 1. EXECUTE (Run the Automated Runner)
We have a powerful runner script to orchestrate experiments.

```bash
# Run with default settings
python3 runner.py

# Run with specific models and parallelism
python3 runner.py --models gemini-2.5-flash gpt-4o deepseek-chat --parallelism 3

# Run quick verification test (replaces test_single.py functionality)
python3 runner.py --models gemini-2.5-flash gpt-4o deepseek-chat --timeout 120 --parallelism 1 --verbose

# Run with verbose output for debugging
python3 runner.py --verbose

# Run full test
python runner.py --models gemini-2.5-flash gpt-4o deepseek-chat --timeout 3600 --parallelism 8 --verbose

# Test a single challenge
python3 runner.py --filter bug-fix --timeout 120 --verbose

# Test only Gemini models
python3 runner.py --models gemini-2.5-flash gemini-1.5-pro --parallelism 2
```

This script will:
1.  Clean and recreate the `experiment/` directory.
2.  Run `zrb chat` for every combination of Model x Challenge.
3.  Automatically execute `verify.sh` or `verify.py` if present in the challenge folder.
4.  Generate a consolidated `REPORT.md` and `results.json` in `experiment/`.

### 2. ANALYZE (Read the Report)
Open `experiment/REPORT.md`.

*   **Green Check (✅)**: The agent finished successfully and passed automated verification.
*   **Warning (⚠️)**: The agent finished, but automated verification failed.
*   **Red Cross (❌)**: The agent crashed or timed out.

### 3. OPTIMIZE (Fix the Root Cause)
**IF AND ONLY IF** a challenge fails or is solved inefficiently:
1.  **Analyze**: Look at the logs linked in the report.
2.  **Refactor `zrb`**: Modify the core framework files.
    -   **Prompts**: `src/zrb/llm/prompt/markdown/`, especially `persona.py` and `mandates.py`
    -   **Tools**: `src/zrb/llm/tool/`
3.  **Retry**: Run `python3 runner.py` again to verify the fix.

## Creating New Challenges
To create a new challenge:
1.  Create a folder `challenges/<name>`.
2.  Add `instruction.md` (The prompt for the agent).
3.  Add `workdir/` (The initial files for the agent).
4.  (Optional) Add `verify.sh` or `verify.py` (Script to assert success).

## Enhanced Runner Features
The `runner.py` script now includes all functionality from `test_single.py`:

1. **Verbose Output**: Use `--verbose` to see real-time execution details and tool call detection
2. **Enhanced Model Configuration**: Better API key handling for gpt-4o and deepseek-chat
3. **Tool Call Detection**: Improved detection of "🧰" emoji in output
4. **Flexible Filtering**: Use `--filter` to test specific challenges
5. **Configurable Timeout**: Adjust timeout per challenge with `--timeout`

## Quick Verification (replaces test_single.py)
To run a quick verification test similar to the old `test_single.py`:
```bash
python3 runner.py --models gemini-2.5-flash gpt-4o deepseek-chat --timeout 120 --parallelism 1 --verbose
```

## Rules of Engagement
1.  **DO NOT MODIFY CHALLENGES**: You are testing `zrb`, not the test itself.
2.  **BE RUTHLESS**: Partial credit is FAILURE.
3.  **SELF-CORRECTION**: If the `runner.py` script fails due to environment issues, fix the environment or the script.
4.  **USE QUICK TESTS FIRST**: Always run a quick verification test to verify your setup before running full experiments.
