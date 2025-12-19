# Gemini-CLI Prompt System Analysis

## Overview
Gemini-CLI employs a highly structured, rule-based prompt system that emphasizes safety, strict adherence to protocols ("Mandates"), and distinct workflows for different types of tasks.

## Components

### 1. Configuration (`packages/core/src/core/prompts.ts`)
-   **Dynamic Construction:** The `getCoreSystemPrompt` function builds the prompt programmatically.
-   **System Override:** Supports a `GEMINI_SYSTEM_MD` environment variable to completely override the default system prompt.
-   **Model Awareness:** Detects "Gemini 3" (preview models) to adjust specific instructions.

### 2. Prompt Structure
The default system prompt is composed of several rigid sections:

1.  **Preamble:** Defines the persona (Interactive/Non-interactive CLI agent).
2.  **Core Mandates:** A critical section defining the "Laws" of the agent:
    -   **Conventions:** Adhere to existing project style.
    -   **Libraries:** Never assume availability; verify first.
    -   **Style & Structure:** Mimic existing code.
    -   **Safety:** Do not revert changes without permission; explain critical commands.
3.  **Primary Workflows:** Explicit guides for common scenarios:
    -   **Software Engineering:** Understand -> Plan -> Implement -> Verify.
    -   **New Applications:** Requirements -> Plan -> User Approval -> Implementation -> Verify.
    -   **Complex Tasks:** Explicitly mandates using the `codebase_investigator` agent for broad analysis.
4.  **Operational Guidelines:**
    -   **Token Efficiency:** Instructions on using `grep`/`head`/`tail` to minimize output.
    -   **Tone:** Professional, concise, no chitchat.
5.  **Context Injection:**
    -   **Sandbox/Git:** Dynamically adds instructions based on the environment.
    -   **Memory:** Appends user-specific memory at the end.

### 3. Specialized Agents (`CodebaseInvestigatorAgent`)
-   Gemini-CLI uses a specialized sub-agent for "deep investigation".
-   This agent has a unique system prompt focused on "Reverse Engineering" and "Mental Modeling".
-   It mandates a **Scratchpad** approach (Checklist, Questions to Resolve, Findings) and strict output schema (JSON report).

### 4. Chat Compression (`packages/core/src/services/chatCompressionService.ts`)
-   **Trigger:** Compress when history exceeds `DEFAULT_COMPRESSION_TOKEN_THRESHOLD` (50% of model limit).
-   **Strategy:** "Split Point" Preservation.
    -   **Preservation:** Keeps the last 30% (`COMPRESSION_PRESERVE_THRESHOLD`) of tokens verbatim.
    -   **Compression:** Summarizes the first 70% of history.
-   **Prompt (`getCompressionPrompt`):**
    -   Similar to Zrb's strategy, it likely asks for a "State Snapshot" (based on function name and shared codebase origins).
    -   Explicit instruction: "First, reason in your scratchpad. Then, generate the <state_snapshot>."
-   **Mechanism:** Replaces the first 70% of messages with a single summary message, effectively creating a "rolling window with summary" history.

## Key Observations
-   **Protocol-Driven:** The system relies heavily on explicit "Mandates" and "Workflows" to control behavior.
-   **Safety & verification:** Strong emphasis on verifying changes (tests, linting) and explaining destructive commands.
-   **Efficiency:** Explicit instructions on how to use shell tools efficiently to save tokens.
-   **Hierarchical:** Uses a "Delegate" pattern (via `codebase_investigator`) for complex understanding tasks.
-   **Hybrid Memory:** Balances summarization with verbatim retention of recent context (70/30 split), which is safer than full summarization for maintaining immediate thread coherence.