# Actionable Items for Zrb Prompt System

Based on the analysis of `gemini-cli` and `opencode`, the following updates are recommended for Zrb's default prompt components (`zrb/src/zrb/config/default_prompt/`).

## 1. Enhance `system_prompt.md` & `interactive_system_prompt.md`

### A. Adopt "Core Mandates" (Source: Gemini-CLI)
Zrb's current mandates are minimal. We should expand them to include strict guidelines on:
-   **Conventions:** Explicitly instructing to mimic existing project style/structure.
-   **Safety:** Requiring explanation before destructive actions.
-   **Verification:** Mandating strict test/lint cycles after changes.
-   **No Assumptions:** Forcing verification of library availability before import.

### B. Define "Primary Workflows" (Source: Gemini-CLI)
Inject specific procedural guides for common tasks:
-   **Engineering:** Understand -> Plan -> Implement -> Verify.
-   **New Projects:** Requirements -> Plan -> Scaffold -> Implement.
This structures the LLM's reasoning process better than generic "be helpful" instructions.

### C. Add Operational Guidelines (Source: Gemini-CLI)
-   **Token Efficiency:** Instruct the model to use `head`, `tail`, or grep flags to minimize output when using shell tools.
-   **Tone:** Enforce a professional, concise CLI persona.

## 2. Improve Context Injection (`zrb/src/zrb/task/llm/prompt.py`)

### A. Auto-Load Project Rules (Source: Opencode)
-   Modify `_construct_system_prompt` to automatically look for and append the content of `ZRB.md` (or `CLAUDE.md`) if found in the project root.
-   This allows users to define persistent, project-specific instructions (coding standards, architectural patterns) without modifying the core Zrb config.

### B. File System Awareness (Source: Opencode)
-   Inject a *brief* file tree (e.g., `ls -F` or `tree -L 2`) into the "System Information" section.
-   This mitigates the "blind agent" problem where the user has to manually feed the file structure or the agent has to waste a turn exploring.

## 3. Refine Summarization & Compaction Strategy

### A. Implement Tool Output Pruning (Source: Opencode)
-   Before triggering a full summary, Zrb should attempt to **prune old tool outputs**.
-   **Logic:** Iterate through history; for tool calls older than $N$ turns (or outside the last $X$ tokens), replace the `output`/`result` with `[TOOL OUTPUT PRUNED]`.
-   **Benefit:** Keeps the *trace* of what happened (commands run) without the massive token cost of file contents or logs, significantly delaying the need for full summarization (which is lossy).

### B. Adopt "Split Point" Preservation (Source: Gemini-CLI)
-   Currently, Zrb seems to replace the *entire* history with a summary + short transcript.
-   **Recommendation:** Ensure the "transcript" portion preserves a significant chunk of recent context (e.g., last 30% of tokens) *verbatim*. Summarization should only target the older 70%.
-   This prevents "context drift" where immediate instructions are lost in a summary.

### C. Enhance Summarization Prompt
-   Zrb's current XML prompt is good. However, explicitly adding a section for **"Irrelevant Paths/Dead Ends"** (like Gemini-CLI's investigator scratchpad) can prevent the agent from re-investigating files it has already ruled out.

## 4. Advanced Features (Long Term)

### A. Specialized Analysis Agent (Source: Gemini-CLI)
-   Create a separate prompt/workflow for "Codebase Investigation".
-   When the user asks for deep analysis, switch to a prompt that enforces a "Scratchpad" methodology and prevents code modification, focusing purely on building a mental model.

### B. Model-Specific Optimization (Source: Opencode)
-   If Zrb supports multiple backends heavily, consider breaking `system_prompt.md` into variations (e.g., `system_prompt_anthropic.md`, `system_prompt_gemini.md`) to leverage specific formatting techniques (like XML tags vs Markdown headers) that work best for each model.