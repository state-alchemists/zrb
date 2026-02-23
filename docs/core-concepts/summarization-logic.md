# LLM History Summarization Logic

This document details the internal mechanics of `zrb`'s LLM history summarization system. The system is designed to maintain conversation context within the token limits of the LLM while strictly adhering to provider constraints (such as role alternation and tool call integrity).

## Overview

The summarization process is a pipeline that transforms a raw list of `ModelMessage` objects into a compressed list of messages. It operates on two levels:

1.  **Message-Level Summarization**: Compressing individual large messages (e.g., massive tool outputs) before they even reach the history limit.
2.  **Conversation-Level Summarization**: Compressing the oldest part of the conversation into a "State Snapshot" when the total token count exceeds the `conversational_token_threshold`.

## The Summarization Pipeline

### 1. Message Summarization
Before assessing the total history size, `zrb` iterates through each message.
- **Target**: `ToolReturnPart` or `TextPart` with excessive content.
- **Action**: If a message part exceeds `message_token_threshold` (default: 50% of conversation threshold), it is summarized individually using a "Message Summarizer" agent.
- **Result**: The original large content is replaced with a summary (e.g., "Summary of tool output: ...").

### 2. History Analysis
The system calculates the total token count of the (possibly message-summarized) history.
- **Triggers**: Summarization is triggered if:
  - Total tokens > `conversational_token_threshold`.
  - OR Number of messages > `summary_window`.

### 3. History Splitting (The "Safe Split")
If summarization is triggered, the history is split into two segments: `to_summarize` (oldest) and `to_keep` (newest).

**Four-Phase Splitting Strategy:**
1. **Phase 1 - Search Backwards from Target Window**: Starting from the ideal split point (keeping `summary_window` messages), search backwards to find a safe split at a conversation turn boundary that stays under 70% of token threshold.
2. **Phase 2 - Search Forwards if No Turn Start**: If no turn start is found, search forwards from the target window to find any safe split (even if not at a turn boundary).
3. **Phase 3 - Find Largest Safe Split**: If no safe split is found near the window, find the largest safe split that stays under 80% of token threshold.
4. **Phase 4 - Best-Effort Approach**: If no safe split exists, use a scoring-based best-effort approach that minimizes damage to incomplete tool pairs.

**Tool Pair Integrity Constraints:**
- **Complete Pairs (Call + Return)**: MUST NOT be separated. Both must be either summarized or kept together.
- **Incomplete Calls (Call without Return)**: Can be summarized if necessary, but prefer to keep them.
- **Orphaned Returns (Return without Call)**: MUST NOT be kept in `to_keep` segment. These indicate corrupted history.

**Safety Validation**: The `is_split_safe()` function validates each potential split point against tool pair relationships using `get_tool_pairs()` to identify call/return relationships.

### 4. Chunked Summarization
The `to_summarize` segment is converted to text and processed.
- **Chunking**: If the text is too large for a single context window, it is split into chunks (e.g., 2000 tokens).
- **Processing**: Each chunk is summarized independently by the "Conversational Summarizer" agent.
- **Consolidation**: The partial summaries are concatenated. If the result is still too large or contains multiple `<state_snapshot>` tags, a final consolidation pass merges them into a single coherent `<state_snapshot>`.

### 5. Context Restoration
The final summary is wrapped in a system message:
> "SYSTEM: Automated Context Restoration... <state_snapshot>..."

### 6. Role Alternation Enforcement
Modern LLMs (like Anthropic's Claude or OpenAI's GPT-4 via strict APIs) require alternating roles: `User` -> `Assistant` -> `User`.
- **Problem**: Summarization or tool usage can sometimes result in consecutive `User` messages (e.g., `User` prompt -> `ToolReturn` (counts as User in some schemas) -> `User` summary).
- **Solution**: The `ensure_alternating_roles` function scans the final message list with **immutability preservation**:
  - **Sequential ModelRequests (User → User)**: Creates a new `ModelRequest` with combined parts: `ModelRequest(parts=list(last_msg.parts) + list(msg.parts))`
  - **Sequential ModelResponses (Assistant → Assistant)**: Uses `dataclasses.replace()` to create a new `ModelResponse` with combined parts
  - **Tool Sequences**: Preserves `User` (prompt) -> `Assistant` (call) -> `User` (return) flows correctly while maintaining message object immutability.

## Flowchart

```mermaid
flowchart TD
    Start[Start: Receive New History] --> MsgSum[1. Message Summarization]
    MsgSum --> CheckTokens{Tokens > Threshold?}
    
    CheckTokens -- No --> End[Return Original History]
    CheckTokens -- Yes --> Split[2. Four-Phase History Split]
    
    Split --> Phase1[Phase 1: Search Backwards<br/>from Target Window]
    Phase1 --> FoundTurnStart{Found Safe<br/>Turn Start?}
    
    FoundTurnStart -- Yes --> Chunking[3. Chunk & Summarize Oldest]
    FoundTurnStart -- No --> Phase2[Phase 2: Search Forwards<br/>for Any Safe Split]
    
    Phase2 --> FoundAnySafe{Found Any<br/>Safe Split?}
    FoundAnySafe -- Yes --> Chunking
    FoundAnySafe -- No --> Phase3[Phase 3: Find Largest<br/>Safe Split Under 80%]
    
    Phase3 --> FoundLargest{Found Largest<br/>Safe Split?}
    FoundLargest -- Yes --> Chunking
    FoundLargest -- No --> Phase4[Phase 4: Best-Effort Split<br/>with Scoring]
    
    Phase4 --> Chunking
    
    Chunking --> Consolidate[4. Consolidate Summaries]
    Consolidate --> CreateSnap[Create Snapshot Message]
    
    CreateSnap --> Merge[Merge Snapshot + Kept Messages]
    Merge --> RoleCheck[5. Role Alternation Check]
    
    RoleCheck --> MergeRoles{Consecutive Roles?}
    MergeRoles -- Yes --> Combine[Combine Messages<br/>(Immutable)]
    MergeRoles -- No --> Final[Final History]
    Combine --> RoleCheck
    
    Final --> End
```

## Edge Case Handling

| Case | Handling Strategy |
| :--- | :--- |
| **Orphaned Tool Return** | `is_split_safe()` rejects any split that would keep an orphaned return (return without call) in the `to_keep` segment. Orphaned returns must be summarized away. |
| **Incomplete Tool Call** | `find_best_effort_split()` allows breaking incomplete calls (call without return) but scores splits to minimize such breaks. Complete pairs are never separated. |
| **No Safe Split Possible** | The four-phase strategy ensures at least some split is found. Phase 4's best-effort approach uses scoring to select the least damaging split when no perfect safe split exists. |
| **Infinite Summarization Loop** | `summarize_long_text` has a strict `depth` limit (default: 5). If max depth is reached, text is forcibly truncated. |
| **Massive Tool Output** | Handled in Step 1. If strict truncation is needed, `limiter.truncate_text` is used before LLM processing. |
| **Mixed Content (Images/Binary)** | `message_to_text` converts complex parts to placeholder text (e.g., `[Image URL: ...]`) to save tokens while preserving semantic awareness. |
| **Prompt Injection** | User input inside the history is treated as data. The system prompts explicitly instruct the LLM to treat the content as "conversation history" to be summarized, minimizing injection risks. |

## Configuration

Control the behavior via `.env` or `config.py`:
- `ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD`: Max tokens before full summarization triggers.
- `ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD`: Max tokens for a single message part.
- `ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW`: Number of recent messages to ideally keep.
