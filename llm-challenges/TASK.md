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

### 1. EXECUTE (Run the Automated Suite)
We have an automated script to reset the environment and run `zrb` against all challenges.

```bash
python3 run_challenges.py
```

This script will:
1.  Clean and recreate the `experiment/` directory.
2.  Copy challenge resources to `experiment/<challenge_name>/`.
3.  Run `zrb chat` autonomously for each challenge.
4.  Capture `stdout` and `stderr` logs to `experiment/<challenge_name>/`.

### 2. EVALUATE (Assert Quality)
After the script finishes, examine the `experiment/` directory.

For **EACH** challenge (e.g., `bug-fix`, `refactor`):
1.  **Read the Evaluation Criteria**: Open `experiment/<challenge_name>/evaluation.md`.
2.  **Inspect Logs**: Check `experiment/<challenge_name>/stdout.log` and `stderr.log` (agent's reasoning/tool usage) .
3.  **Inspect Artifacts**: Check the files in `experiment/<challenge_name>/workdir/` (or the root of the experiment folder if no workdir dir).
    *   *Did the code change as expected?*
    *   *Does the fix work?*
    *   *Is the report written correctly?*

*   **PASS:** The agent met ALL criteria in `evaluation.md`.
*   **FAIL:** The agent missed ANY criterion, hallucinated, crashed, or the code doesn't work.

### 3. OPTIMIZE (Fix the Root Cause)
**IF AND ONLY IF** a challenge fails or is solved inefficiently:
1.  **Analyze**: Why did it fail?
    -   Ambiguous System Prompt?
    -   Confusing Tool Docstring?
    -   Missing Context?
    -   Poor Tool Selection?
2.  **Refactor `zrb`**: Modify the core framework files to guide the LLM better.
    -   **Prompts**: `src/zrb/llm/prompt/markdown/` (e.g., `mandate.md`, `persona.md`) relative to project root.
    -   **Tools**: `src/zrb/llm/tool/` (Edit Python docstrings/signatures) relative to project root.
3.  **Retry**: Run `python3 run_challenges.py` again to verify the fix.

## Rules of Engagement
1.  **DO NOT MODIFY CHALLENGES**: You are testing `zrb`, not the test itself. The `instruction.md` and `evaluation.md` are IMMUTABLE STANDARDS.
2.  **BE RUTHLESS**: Partial credit is FAILURE. The code must run, the features must exist, the tone must be correct.
3.  **SELF-CORRECTION**: If the `run_challenges.py` script fails due to environment issues, fix the environment or the script, but do not alter the challenge logic.