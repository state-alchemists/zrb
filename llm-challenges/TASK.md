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

Perform the following loop for **EACH** challenge:

### 1. SETUP (Reset Environment)
Ensure a clean state for the challenge (e.g., `refactor`).
```bash
# Example for 'refactor' challenge
rm -rf experiment/refactor
mkdir -p experiment/refactor
cp -r challenges/refactor/* experiment/refactor/
```

### 2. EXECUTE (Run the Agent)
Run the `zrb` agent against the challenge instructions.
**CRITICAL:** Use `--interactive false` and `--yolo true` to ensure autonomous execution.

```bash
# Navigate to the resources directory of the experiment
cd experiment/refactor/resources

export ZRB_LOGGING_LEVEL=DEBUG
export ZRB_LLM_SHOW_TOOL_CALL_RESULT=true
export ZRB_LLM_SHOW_TOOL_CALL_PREPARATION=true

# Read the instruction and execute
zrb llm chat \
    --interactive false \
    --yolo true \
    --message "$(cat ../instruction.md)"
```

### 3. EVALUATE (Assert Quality)
Read the `evaluation.md` file in the original challenge directory (e.g., `challenges/refactor/evaluation.md`).
**Compare the actual outcome** (files in `experiment/refactor/resources/`, logs) against the **Expected Outcome**.

*   **PASS:** The agent met ALL criteria perfectly.
*   **FAIL:** The agent missed ANY criterion, hallucinated, or crashed.

### 4. OPTIMIZE (Fix the Root Cause)
**IF AND ONLY IF** a challenge fails:
1.  **Analyze**: Why did it fail?
    -   Ambiguous System Prompt?
    -   Confusing Tool Docstring?
    -   Missing Context?
2.  **Refactor `zrb`**: Modify the core framework files to guide the LLM better.
    -   **Prompts**: `src/zrb/llm/prompt/markdown/` (e.g., `mandate.md`, `persona.md`) relative to project root.
    -   **Tools**: `src/zrb/llm/tool/` (Edit Python docstrings/signatures) relative to project root.
3.  **Retry**: Go back to Step 1 (SETUP) and repeat until PASS.

## Rules of Engagement
1.  **DO NOT MODIFY CHALLENGES**: You are testing `zrb`, not the test itself. The `instruction.md` and `evaluation.md` are IMMUTABLE STANDARDS.
2.  **BE RUTHLESS**: Partial credit is FAILURE. The code must run, the features must exist, the tone must be correct.
3.  **SELF-CORRECTION**: If you (the AI Agent running this test) encounter errors running the commands, fix your command usage immediately.
