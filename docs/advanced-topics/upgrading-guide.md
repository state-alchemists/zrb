🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Upgrading Guide

# Upgrading Guide

What to change in an existing setup when moving to a newer Zrb release. Only the
releases that need action are listed — anything not mentioned here is
source-compatible.

## Table of Contents

- [Upgrading to 2.54.0](#upgrading-to-2540)
- [Upgrading from 1.x.x to 2.x.x](#upgrading-from-1xx-to-2xx)

---

## Upgrading to 2.54.0

2.54.0 collapses the system prompt from six rule sections to three and removes the
tool-guidance registry. Task authoring, `CmdTask`, `cli`, `Env`, and `Input` are
unaffected. Two areas need attention.

### The tool-guidance API is gone

`ToolGuidance` and the four `add_tool_guidance*` methods were removed with no
shim, so calls to them raise `AttributeError` / `ImportError` rather than
silently doing nothing.

| Before | After |
|---|---|
| `from zrb import ToolGuidance` | *(removed)* |
| `task.add_tool_guidance(ToolGuidance(...))` | put the guidance in the tool's **docstring** |
| `task.add_tool_guidance_factory(lambda ctx: ...)` | `task.prompt_manager.register_section(name, provider)` |
| `task.add_tool_guidance_section_factory(...)` | `task.prompt_manager.register_section(name, provider)` |
| `task.prompt_manager.add_tool_group(name=...)` | *(removed — groups no longer exist)* |
| `task.prompt_manager.tool_names = {...}` | *(removed — nothing filters on it)* |

Per-tool guidance moves into the function's docstring, which pydantic-ai
serializes alongside the JSON schema on every request:

```python
def check_stock(warehouse_id: str, sku: str) -> dict:
    """Look up on-hand stock for one SKU in one warehouse.

    Always pass warehouse_id — a lookup without it scans every site and times
    out. An empty result means no stock on hand, not an error.
    """
    ...
```

Cross-cutting policy that is not about one tool becomes a registered section:

```python
task.prompt_manager.register_section(
    "tool_policy",
    lambda ctx: "## Inventory rules\n- Never quote stock without a warehouse.",
)
```

Then place `tool_policy` in `ZRB_LLM_INCLUDE_SECTIONS` at the position you want.

### Four prompt sections were retired

`mandate`, `git_mandate`, `journal_mandate`, and `tool_guidance` no longer exist.

| Retired section | Where its content went |
|---|---|
| `mandate` | folded into `workflow` (the Priority Order now opens it) |
| `git_mandate` | enforced by the shell tool policy; the one prompt-side rule moved to `workflow` |
| `journal_mandate` | replaced by the `LogActivity` and `WriteJournalNote` tools |
| `tool_guidance` | tool docstrings, plus a `Tool usage` block in `workflow` |

A pinned `ZRB_LLM_INCLUDE_SECTIONS` or sub-agent `inherit_sections` naming any of
them still parses. The name falls through to the custom-section path, so what
happens depends on whether a markdown file resolves for it:

- **No override file** — the section composes to `""` and logs a warning at
  compose time. Nothing crashes; the entry just contributes nothing.
- **You have an override** (`mandate.md` in `ZRB_LLM_PROMPT_DIR`, or
  `ZRB_LLM_PROMPT_MANDATE`) — it is still emitted, at that position, as a
  file-backed custom section. Your customization survives untouched.

Either way, update the list to the new defaults:

```bash
export ZRB_LLM_INCLUDE_SECTIONS="persona,workflow,examples,system_context,project_context"
```

`ZRB_LLM_INCLUDE_JOURNAL_REMINDER` is removed along with its hook; the journal
tools make the reminder unnecessary. `ZRB_LLM_JOURNAL_ENABLED` still works and
now unregisters the three journal tools instead of dropping a prompt section.

**Careful with overrides.** If you overrode a retired prompt file
(`mandate.md`, `git_mandate.md`, `journal_mandate.md`) *and* you rely on the
default section list, your override silently stops being read — the name is no
longer in the defaults, so nothing resolves it. Either keep the name in an
explicit `ZRB_LLM_INCLUDE_SECTIONS` (it then works as a custom section, see
above) or move the content into a `workflow.md` override.

See [ADR-0045](../adr/adr-0045.md) and [ADR-0053](../adr/adr-0053.md) for the
reasoning.

---

## Upgrading from 1.x.x to 2.x.x

Zrb 2.x is largely **backwards-compatible** with 1.x for task authoring. If you only use `Task`, `CmdTask`, `LLMTask`, `cli`, `Env`, and `Input` types, your existing `zrb_init.py` files should work without changes.

The areas that changed are in the LLM and UI layers:

### LLM UI Module Path

The UI classes were moved from `zrb.llm.app` to `zrb.llm.ui`.

| 1.x.x import | 2.x.x import |
|---|---|
| `from zrb.llm.app import SimpleUI` | `from zrb.llm.ui import SimpleUI` |
| `from zrb.llm.app import EventDrivenUI` | `from zrb.llm.ui import EventDrivenUI` |
| `from zrb.llm.app import PollingUI` | `from zrb.llm.ui import PollingUI` |

If you only interact with the built-in `llm_chat` task (i.e. you don't subclass or import UI classes directly), no change is needed.

### Hooks Timeout Unit

`ZRB_HOOKS_TIMEOUT` changed from **seconds** to **milliseconds** in 2.20.0.

| 1.x.x | 2.x.x |
|---|---|
| `ZRB_HOOKS_TIMEOUT=30` (30 seconds) | `ZRB_HOOKS_TIMEOUT=30000` (30 seconds) |

Update your environment variable if you had set a custom timeout.

### New Features in 2.x

These are additions, not breaking changes, but worth knowing:

| Feature | How to use |
|---|---|
| Multiple UIs | `llm_chat.append_ui_factory(...)` — broadcast to CLI + Telegram simultaneously |
| Approval channels | `llm_chat.append_approval_channel(...)` — first approval from any channel wins |
| Rewind/Snapshot | `/rewind` command in TUI; `enable_rewind=True` on `LLMChatTask` |
| MCP servers | `mcp-config.json` — see [MCP Support](mcp-support.md) |
| Worktree tools | `EnterWorktree` / `ExitWorktree` tools available in agent sessions |
| PowerShell autocomplete | `zrb shell autocomplete powershell` |

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Upgrading Guide
