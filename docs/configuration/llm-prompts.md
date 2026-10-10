🔖 [Documentation Home](../README.md) > [Configuration](./) > [LLM Configuration](llm-config.md) > Prompts

# LLM System Prompts

What the system prompt is built from, and every way to change it.

## Table of Contents

- [System Prompts & Identity](#system-prompts--identity)
  - [Identity Variables](#identity-variables)
  - [Prompt Customization Hierarchy](#prompt-customization-hierarchy)
  - [Overridable Prompts](#overridable-prompts)
  - [Prompt Component Configuration](#prompt-component-configuration)
  - [Prompt Profile (matching the prompt to the model)](#prompt-profile-matching-the-prompt-to-the-model)
  - [Programmatic Prompt Customization](#programmatic-prompt-customization)
  - [Restricting the toolbox (`ZRB_LLM_TOOLS`)](#restricting-the-toolbox-zrb_llm_tools)

---

## System Prompts & Identity

### Identity Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_ASSISTANT_NAME` | Display name for AI assistant | `Zrb` |
| `ZRB_LLM_ASSISTANT_JARGON` | Tagline or motto | Root group description |
| `ZRB_LLM_ASSISTANT_ASCII_ART` | ASCII banner art name | `default` (built-in) |
| `ZRB_ASCII_ART_DIR` | Directory for custom ASCII art files | `.zrb/ascii-art` |

### Prompt Customization Hierarchy

First found wins:

| Priority | Location | Description |
|----------|----------|-------------|
| 1 (highest) | `ZRB_LLM_PROMPT_DIR` | Local directory override |
| 2 | `ZRB_LLM_PROMPT_<NAME>` | Environment variable |
| 3 | `ZRB_LLM_BASE_PROMPT_DIR` | Shared/org directory |
| 4 (lowest) | Package default | Built-in prompts |

### Overridable Prompts

- `persona`
- `principle`
- `workflow`
- `example`
- `profile` (always resolves as `profile.{name}.md`; see [Prompt Profile](#prompt-profile-matching-the-prompt-to-the-model))
- `conversational_summarizer`
- `message_summarizer`
- `file_extractor`
- `repo_extractor`
- `repo_summarizer`
- `web_summarizer`

### Prompt Component Configuration

The system prompt is an **ordered list of sections**; what each section holds, what is deliberately *not* a section, and how to compose them from Python are explained in [Programming the Prompt → Rung 5](../llm/programming-the-prompt.md#rung-5--composing-sections-with-promptmanager).

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_INCLUDE_SECTIONS` | Comma-separated, order-sensitive list of sections to include. Remove a name to drop a section; rewrite the list to reorder. The set is fixed: an unknown (e.g. misspelled) name logs a warning at compose time and is skipped. Programmatic twin: `CFG.LLM_INCLUDE_SECTIONS` (a `list[str]`) | `persona,principle,workflow,example,profile,system_context,project_context` |
| `ZRB_LLM_PROMPT` | Comma-separated extra prompts appended after every built-in section — the env twin of `prompt_registry`. Empty means none. Content that won't fit a comma value (callables, structured middleware) belongs in `zrb_init.py` via `prompt_registry`. See [LLM Component Collections](./llm-collections.md). | (empty) |

```bash
# Strip demonstrations and project context (e.g. for benchmark runners).
export ZRB_LLM_INCLUDE_SECTIONS="persona,workflow,system_context"

# Personality-only: just persona.
export ZRB_LLM_INCLUDE_SECTIONS="persona"
```

### Prompt Profile (matching the prompt to the model)

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_PROFILE` | Prompt profile: `minimal`, `standard`, `capable`, or `auto`. Swaps the `profile` section and, for `minimal` only, drops the delegate (sub-agent) tools. An unrecognized value falls back to `standard` | `auto` |

What each profile changes and how `auto` reads a model id: [Programming the Prompt → Rung 7](../llm/programming-the-prompt.md#rung-7--file-backed-sections-and-profiles).

### Programmatic Prompt Customization

Each task exposes its `PromptManager` as `task.prompt_manager`; `prompt_registry` in `zrb_init.py` sets the default every task starts from. Appending content, per-turn live context, and overriding a built-in prompt file are covered in [Programming the Prompt](../llm/programming-the-prompt.md) (rungs 5–7); the lookup chain a file override follows is the [hierarchy above](#prompt-customization-hierarchy).

### Restricting the toolbox (`ZRB_LLM_TOOLS`)

`ZRB_LLM_TOOLS` is the env twin of `tool_registry`: a **name allowlist** of static tools. Empty (default) means all built-in + registered tools.

```bash
export ZRB_LLM_TOOLS="Shell,Read,Write,Grep,Glob,TodoWrite"
```

Names are the PascalCase tool names (the `Tool` column in [Built-in LLM Tools](../llm/extending-the-llm.md#built-in-llm-tools)). Per-run factory and toolset tools have no static name, so they are not filtered. To add or drop individual tools, use `tool_registry` in `zrb_init.py`; see [LLM Component Collections](./llm-collections.md).
