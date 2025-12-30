# Zrb LLM Challenge

This directory contains a framework for testing and evaluating `zrb llm ask`.

## Overview of `zrb llm ask`

The `zrb llm ask` command is a powerful tool for interacting with Large Language Models (LLMs) to perform various tasks, especially those related to software engineering. It uses the `LLMTask` class to orchestrate interactions.

The process generally follows these steps:
1. **History Management**: Loads conversation history (long-term context, narrative summary, and raw chat log).
2. **Context Enrichment**: Periodically updates the long-term context with stable facts.
3. **History Summarization**: Condenses old chat logs into a narrative summary.
4. **Prompt Construction**: Builds a system prompt using persona, base system prompt, special instructions, and a context block (system info, long-term context, summary, and referenced files).
5. **Agent Execution**: Uses a `pydantic-ai` agent with defined tools to execute the task.

## Iterative Improvement Goal

The ultimate goal of these challenges is to **improve `zrb`'s internal prompts and tool definitions**. 

You should run these challenges to identify weaknesses in how `zrb` understands instructions or uses tools. If a challenge fails:
1.  **Analyze the Failure**: Did the LLM misunderstand the request? Did it misuse a tool? Did it hallucinate?
2.  **Modify Zrb**:
    -   **Prompts**: specific files in `src/zrb/config/default_prompt/` (e.g., `system_prompt.md`, `persona.md`).
    -   **Tool Docstrings**: The Python docstrings in `src/zrb/builtin/llm/tool/*.py`. These are what the LLM sees as "instructions" for using tools.
3.  **Retry**: Run the challenge again.
4.  **Repeat**: Continue until **ALL** challenges pass successfully and consistently.

### Important Files to Modify

These are the files you will likely need to tune:

- **System Prompts**: `src/zrb/config/default_prompt/`
    - `system_prompt.md`: The core instruction set.
    - `persona.md`: The personality and role definition.
- **Tool Definitions**: `src/zrb/builtin/llm/tool/`
    - Check files like `file.py`, `code.py`, `web.py` etc.
    - Improve the docstrings (function descriptions, argument descriptions) to be clearer and more robust against misuse.

## How to Run a Challenge

Follow these steps to run a challenge:

1. **Setup Experiment Directory**:
   Copy a use case from the `challenges` folder into the `experiment` directory.
   ```bash
   cp -r challenges/refactor experiment/
   ```

2. **Move to Experiment Directory and run `zrb llm ask`** (IMPORTANT: always provide `start-new` and `yolo` parameters when calling `zrb llm ask`):
   ```bash
   export ZRB_LOGGING_LEVEL=DEBUG
   export ZRB_LLM_SHOW_TOOL_CALL_RESULT=true
   cd experiment/refactor/resources && zrb llm ask --start-new true --yolo true "$(cat ../instruction.md)"
   ```

3. **Evaluate the Result**:
   Check the changes made to the files in the `resources` directory (or new files created) and compare them against the criteria in `evaluation.md`.

## Challenges

### Software Engineering
- **`refactor`**: Refactor a legacy "spaghetti code" ETL script (`legacy_etl.py`).
    - *Goal*: Modularize code, fix global configs, improve parsing, and add typing.
- **`bug-fix`**: Fix a race condition in an async inventory system (`inventory_system.py`).
    - *Goal*: Use concurrency control (Locks) to prevent negative stock.
- **`feature`**: Implement CRUD endpoints for a FastAPI Todo App (`todo_app.py`).
    - *Goal*: Add POST, PUT, DELETE endpoints with proper Pydantic models.

### General Tasks
- **`research`**: Conduct research on "Solid State Batteries".
    - *Goal*: Produce a structured markdown report covering timelines, players, and hurdles.
- **`copywriting`**: Write a launch blog post for "Zrb-Flow".
    - *Goal*: Creative writing with specific tone and structural requirements.
