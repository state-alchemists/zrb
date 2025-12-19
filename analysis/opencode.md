# Opencode Prompt System Analysis

## Overview
Opencode's prompt system is characterized by its deep context awareness and model-specific adaptability. It focuses on automatically providing the agent with a comprehensive view of the environment and project conventions.

## Components

### 1. Dynamic System Prompt (`packages/opencode/src/session/system.ts`)
Opencode constructs the prompt by layering several dynamic components:

-   **Model-Specific Base:** Selects a base prompt file (`anthropic.txt`, `gemini.txt`, `beast.txt`) tailored to the specific LLM provider.
-   **Spoofing:** Can inject headers to "spoof" or align with specific model training.
-   **Environment Context:** Automatically injects a `<env>` block containing:
    -   Working directory.
    -   Git status.
    -   **File Tree:** Runs `ripgrep` to embed a visualization of the file structure (up to 200 files) directly in the prompt.
-   **Project Rules (Custom Context):**
    -   Automatically looks for and loads `AGENTS.md`, `CLAUDE.md`, and `CONTEXT.md`.
    -   Checks global configuration (`~/.claude/CLAUDE.md`).
    -   Allows wildcard-based loading of instructions via config.

### 2. Agent Generation (`packages/opencode/src/agent/generate.txt`)
-   Includes a meta-prompt for generating *new* agents.
-   Positions the LLM as an "elite agent architect".
-   Generates a JSON configuration with `identifier`, `whenToUse`, and a custom `systemPrompt` for the new agent.

### 3. Compaction & Pruning (`packages/opencode/src/session/compaction.ts`)
-   **Trigger:** Checks for "overflow" (`isOverflow`) based on context window and output limits.
-   **Pruning Strategy (Unique):**
    -   Before full compaction, it runs a `prune` function.
    -   It iterates backwards through history.
    -   Once it finds enough "protected" recent tool calls (last ~40k tokens), it *erases* the output of older tool calls, replacing them with `[TOOL OUTPUT PRUNED]`.
    -   This allows maintaining the *fact* that a tool was called without paying the token cost of the output.
-   **Compaction Strategy:**
    -   If pruning isn't enough, it triggers a "compaction" turn.
    -   The agent is asked to "Provide a detailed prompt for continuing our conversation...".
    -   The system then effectively **restarts** the session with this new detailed prompt as the starting point.
-   **Prompt (`compaction.txt`):** Simple instructions asking for "What was done", "Current work", "Modified files", and "Next steps".

## Key Observations
-   **Context-First:** The most distinct feature is the aggressive injection of context (File Tree + `CLAUDE.md`) without user intervention.
-   **Model Optimization:** Handles model differences at the infrastructure level.
-   **Standardization:** Leverages standard files (`CLAUDE.md`) for persistent conventions.
-   **Tool Output Pruning:** A highly effective optimization for coding agents, as tool outputs (like `cat file.txt`) are often massive but become irrelevant once the information is used.