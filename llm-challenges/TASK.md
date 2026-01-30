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
python3 runner.py --models gemini-1.5-pro gpt-4 --parallelism 8
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
    -   **Prompts**: `src/zrb/llm/prompt/markdown/`
    -   **Tools**: `src/zrb/llm/tool/`
3.  **Retry**: Run `python3 runner.py` again to verify the fix.

## Creating New Challenges
To create a new challenge:
1.  Create a folder `challenges/<name>`.
2.  Add `instruction.md` (The prompt for the agent).
3.  Add `workdir/` (The initial files for the agent).
4.  (Optional) Add `verify.sh` or `verify.py` (Script to assert success).

## Rules of Engagement
1.  **DO NOT MODIFY CHALLENGES**: You are testing `zrb`, not the test itself.
2.  **BE RUTHLESS**: Partial credit is FAILURE.
3.  **SELF-CORRECTION**: If the `runner.py` script fails due to environment issues, fix the environment or the script.
