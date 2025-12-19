# Zrb Prompt System Analysis

## Overview
Zrb's prompt system is designed to be modular and context-aware, dynamically assembling prompts based on configuration, user input, and conversation history.

## Components

### 1. Configuration (`zrb/src/zrb/config/llm_config.py`)
-   **Centralized Config:** The `LLMConfig` class manages all LLM-related settings, including default models, providers, and prompts.
-   **Default Prompts:** Prompts are loaded from markdown files located in `zrb/src/zrb/config/default_prompt/`:
    -   `system_prompt.md`: For single-turn tasks (`llm-ask`).
    -   `interactive_system_prompt.md`: For conversational sessions (`llm-chat`).
    -   `persona.md`: Defines the agent's identity.
    -   `summarization_prompt.md`: For summarizing history.

### 2. Prompt Construction (`zrb/src/zrb/task/llm/prompt.py`)
The `_construct_system_prompt` function is the core builder, assembling the final system message in the following order:

1.  **Persona:** Retrieved from `persona.md` (or overridden by task config).
2.  **Base System Prompt:** Retrieved from `system_prompt.md` or `interactive_system_prompt.md`.
3.  **Special Instructions:**
    -   Includes a "SPECIAL INSTRUCTION" section.
    -   Injects **Active Workflows** (instructions for enabled tools/workflows).
4.  **Available Workflows:**
    -   Lists inactive workflows in "AVAILABLE WORKFLOWS" section, allowing the LLM to know what else it *could* do if asked.
5.  **Context:**
    -   **System Information:** OS, Python version, Current Directory, Current Time.
    -   **Long Term Note:** Persistent memories from `ConversationHistory`.
    -   **Contextual Note:** Summaries of recent conversation.
    -   **Appendixes:** Content of files/directories referenced by the user (e.g., `@path/to/file`).

### 3. User Message Handling (`_get_user_message_prompt`)
-   **Resource Expansion:** Detects `@path` references in the user message.
-   **Content Injection:** Reads referenced files/directories.
-   **Placeholder Replacement:** Replaces `@path` in the message with `[Reference N: filename]`.
-   **Appendix Appending:** Adds the actual content to the "Appendixes" section of the System Prompt.
-   **Wrapper:** Wraps the final user message with metadata (CWD, Time).

### 4. History Summarization (`zrb/task/llm/history_summarization.py`)
-   **Trigger:** Configurable token threshold (`default_history_summarization_token_threshold`).
-   **Strategy:** "State Snapshot" + "Recent Transcript".
-   **Prompt (`summarization_prompt.md`):**
    -   Highly structured XML output format.
    -   Requires **Scratchpad Reasoning** (`<scratchpad>`) before generating the summary.
    -   **Key Sections:** `<overall_goal>`, `<key_knowledge>`, `<file_system_state>`, `<recent_actions>`, `<current_plan>`.
-   **Mechanism:** The generated summary and a short transcript of recent messages become the *only* context for the next turn, effectively discarding the raw history. This is an aggressive but token-efficient strategy.

## Prompt Content Analysis

-   **System Prompt (`system_prompt.md`):** Focuses on "Tool-Centric" behavior, "Sequential Execution", and "Execute & Verify Loop". Explicitly instructs *not* to describe actions, just report results.
-   **Interactive Prompt (`interactive_system_prompt.md`):** Similar structure but emphasizes "Clarification" and "Planning".
-   **Persona (`persona.md`):** Generic "helpful and efficient AI agent".

## Key Observations
-   **Separation of Concerns:** Distinct prompts for single-turn vs. interactive modes.
-   **Dynamic Context:** heavily relies on injecting context (files, history, system info) into the system prompt rather than the user message.
-   **Workflow Integration:** "Workflows" (likely tools or scripts) are dynamic components of the prompt.
-   **Structured Summarization:** The summarization prompt is notably advanced, treating the LLM as a "State Manager" rather than just a text summarizer.