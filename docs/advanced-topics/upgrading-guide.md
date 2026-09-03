🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Upgrading Guide

# Upgrading Guide

What to change in an existing setup when moving to a newer Zrb release. Only the releases that need action are listed — anything not mentioned here is source-compatible.

## Table of Contents

- [Upgrading to 3.0.0](#upgrading-to-300)
- [Upgrading to 2.58.0](#upgrading-to-2580)
- [Upgrading to 2.54.0](#upgrading-to-2540)
- [Upgrading from 1.x.x to 2.x.x](#upgrading-from-1xx-to-2xx)

---

## Upgrading to 3.0.0

3.0.0 removes `LLMConfig`, consolidates UI construction into `UIConfig`, renames the hook and search-directory APIs to match every other family's verb set, and renames the UI and approval-channel contracts to the `Any<Thing>` convention. All of it fails loudly — `AttributeError`, `TypeError`, or `ImportError` — so a green test run means you are done. Plain `Task`/`CmdTask` task authoring is unaffected.

### `LLMConfig`/`llm_config` is gone — `CFG` is the only LLM configuration object

| Before | After |
|---|---|
| `llm_config.model` | `CFG.LLM_MODEL` |
| `llm_config.small_model` | `CFG.LLM_SMALL_MODEL` |
| `llm_config.multimodal_model` | `CFG.LLM_MULTIMODAL_MODEL` |
| `llm_config.api_key` | `CFG.LLM_API_KEY` |
| `llm_config.base_url` | `CFG.LLM_BASE_URL` |
| `llm_config.provider` | `CFG.LLM_PROVIDER` (new, `ZRB_LLM_PROVIDER`) |
| `llm_config.resolve_model(m)` | `resolve_configured_model(m)` (`zrb.llm.config.model_resolver`) |
| `llm_config.model_getter = f` | `task.model_getter = f` (per task, not process-wide) |
| `llm_config.model_renderer = f` | `task.model_renderer = f` (per task, not process-wide) |
| `LLMTask(llm_config=...)` | `LLMTask(model_getter=..., model_renderer=...)` |

`llm_config.model_settings` had no real reader and has no replacement. `model_getter`/`model_renderer` are now **task-scoped**: a `zrb_init.py` that set them once to affect every agent process-wide must set them per task instead — *or* set them once on `model_resolver` (`zrb.llm.config.model_resolver.model_resolver`) for a process-wide default that also reaches sub-agent delegation, which has no task of its own:

```python
from zrb.llm.config.model_resolver import model_resolver

model_resolver.model_getter = my_model_getter
model_resolver.model_renderer = my_model_renderer
```

A task's own `model_getter`/`model_renderer`, when set, still applies on top of this default for that task specifically.

### `UIConfig` replaces individual UI constructor parameters

`BaseUI.__init__` and `LLMChatTask.__init__` each dropped ~15-20 individual UI parameters (`*_commands`, `yolo_xcom_key`, `assistant_name`, `is_yolo`, `show_ollama_models`, `show_pydantic_ai_models`, ...) for one `ui_config: UIConfig | None`.

```python
# Before
LLMChatTask(ui_commands=UICommands(exit="/quit"))

# After
LLMChatTask(ui_config=UIConfig(exit_commands=["/quit"]))
```

| Before | After |
|---|---|
| `LLMChatTask(ui_commands=UICommands(exit="/quit"))` | `LLMChatTask(ui_config=UIConfig(exit_commands=["/quit"]))` |
| `task.yolo_xcom_key` | `task.ui_config.yolo_xcom_key` |
| `task.show_ollama_models` | `task.ui_config.show_ollama_models` |
| `UIConfig.minimal()` | `UIConfig(exit_commands=["/exit"], ...)` |

`UICommands` and `UI_COMMAND_CFG_ATTRS` are deleted, including from `zrb`'s top-level exports. `ui_config` is a settable, type-checked property, so `llm_chat.ui_config = UIConfig(...)` works on the built-in task too.

### The hook family drops `register`/`clear_manual`

| Before | After |
|---|---|
| `hook_registry.register(...)` | `hook_registry.add_hook(...)` |
| `hook_manager.register(...)` | `hook_manager.add_hook(...)` |
| `hook_registry.clear_manual()` | `hook_registry.clear()` |

### `get_search_directories()` is gone

`HookManager`, `SkillManager`, and `SubAgentManager` each now have exactly one `search_dirs` property instead.

| Before | After |
|---|---|
| `manager.get_search_directories()` | `manager.search_dirs` |
| `sub_agent_manager.root_dir` | `sub_agent_manager.scan_root` |

Assigning `search_dirs` (now settable on all three, not just at construction) invalidates any completed scan, so the next read/scan picks it up.

### `LLMChatTask` collection setters are renamed

Every ordered collection on `LLMChatTask` (tools, toolsets, history processors, triggers, custom commands, hook factories, tool policies, response handlers, argument formatters, UIs) now has the full `append_X`/`prepend_X`/`set_X`/`remove_X` verb set. The single-value slots below changed shape:

| Before | After |
|---|---|
| `task.set_ui(x)` | `task.set_uis([x])` |
| `task.set_ui_factory(x)` | `task.ui_factories = [x]` |
| `task.set_approval_channel(x)` | `task.approval_channels = [x]` |
| `task.set_history_manager(x)` | `task.history_manager = x` |
| `task.prompt_manager if task.has_prompt_manager else None` | `task.prompt_manager` |

`prompt_manager`, `hook_manager`, `llm_limiter`, and `markdown_theme` are now settable, type-checked properties too — `llm_chat.prompt_manager = pm` works on the built-in task.

### The UI and approval-channel contracts are `AnyUI`/`AnyApprovalChannel`

Both are now **ABCs** — a custom implementation must subclass them (an incomplete subclass now fails at instantiation with `TypeError`, not at first call with `NotImplementedError`).

| Before | After |
|---|---|
| `from zrb.llm.tool_call.ui_protocol import UIProtocol` | `from zrb import AnyUI` |
| `from zrb.llm.approval.approval_channel import ApprovalChannel` | `from zrb.llm.approval import AnyApprovalChannel` |
| `class MyUI(UIProtocol):` | `class MyUI(AnyUI):` (or subclass `BaseUI`/`SimpleUI`/`EventDrivenUI`/`PollingUI`, which already do) |
| `class MyChannel(ApprovalChannel):` | `class MyChannel(AnyApprovalChannel):` |

If you only use the built-in `llm_chat` task and never subclassed these directly, no change is needed — every built-in UI and approval channel already inherits the new base.

### Worth knowing (no action needed)

- **`CFG` assignments now fail fast.** An unknown `CFG.UPPERCASE` name raises `AttributeError` naming the closest real knob; a value the field can't accept raises `ValueError` at the assignment site. This only surfaces bugs that were previously silent no-ops.
- **A broken `zrb_init.py` is reported precisely, not hidden — and still not fatal.** The file, line, and exception type now print to stderr; the CLI still starts with whatever partial state resulted, same as before.
- **13 internal `raise Exception(...)` sites now raise typed errors** (`SearchToolError`, `RuntimeError`, `ValueError`) — a bare `except Exception` still catches them.
- **6 config mixin classes were renamed** (`ConfigLLMContent` → `LLMContentMixin`, etc.) — only relevant if you imported one directly from `zrb.config.mixins`.



Three changes need action. All fail loudly — `AttributeError`, `TypeError`, or `ImportError` — rather than silently doing the wrong thing, so a green test run means you are done. Env vars and prompt files are unaffected.

### `add_X` on ordered collections is `append_X` or `prepend_X`

The 22 one-line aliases are gone. `add_` had stopped meaning one thing — it forwarded to `append_` nineteen times and to `prepend_` three times — so the name no longer told you where your handler landed. Position is now in the name.

| Before | After |
|---|---|
| `task.add_tool(...)` | `task.append_tool(...)` |
| `task.add_tool_factory(...)` | `task.append_tool_factory(...)` |
| `task.add_toolset(...)` | `task.append_toolset(...)` |
| `task.add_toolset_factory(...)` | `task.append_toolset_factory(...)` |
| `task.add_hook_factory(...)` | `task.append_hook_factory(...)` |
| `task.add_history_processor(...)` | `task.append_history_processor(...)` |
| `task.add_trigger(...)` | `task.append_trigger(...)` |
| `task.add_custom_command(...)` | `task.append_custom_command(...)` |
| `task.prompt_manager.add_prompt(...)` | `task.prompt_manager.append_prompt(...)` |
| `task.add_response_handler(...)` | **`task.prepend_response_handler(...)`** |
| `task.add_tool_policy(...)` | **`task.prepend_tool_policy(...)`** |
| `task.add_argument_formatter(...)` | **`task.prepend_argument_formatter(...)`** |

The three bold rows are the reason for the change: they always inserted at the front, and `add_` hid it. If you were relying on `add_` appending them, you want `append_` instead — those exist too.

`add_X` on **unordered registries** is unchanged: `skill_manager.add_skill`, `sub_agent_manager.add_agent`, `Group.add_task`, `Group.add_group`, `PromptManager.add_live_context`.

### Task constructors are keyword-only after `name`

```python
Task("build")                 # still fine
Task(name="build", color=5)   # still fine
Task("build", 5)              # TypeError
```

Applies to `Task`, `CmdTask`, `LLMTask`, `LLMChatTask`, `RsyncTask`, `Scaffolder`, `Scheduler`, `HttpCheck`, `TcpCheck`, `BaseTrigger`, `BaseTask` and `make_task`. `LLMChatTask` had 73 positionally-passable parameters, so any future insertion would otherwise have been a silent breaking change.

### Two renames

| Before | After |
|---|---|
| `RsyncTask(auto_render_shell=...)` | `RsyncTask(render_shell=...)` |
| `from zrb import AnyAttr` | `from typing import Any`, or the specific `StrAttr` / `BoolAttr` / … |

`AnyAttr` was defined as `Any \| fstring \| Callable[..., Any]`, which collapses to plain `Any` — it constrained nothing while looking like it did. `fstring` is unchanged.

### Worth knowing (no action needed)

- **`py.typed` ships**, so `mypy`/`pyright` now actually check your zrb usage. Expect to see real errors the first time — they were always there, just invisible.
- **Collections accept any `Sequence`.** `upstream=(a, b)` and `a >> (b, c)` used to store the tuple as if it were a task and fail later with `'tuple' object has no attribute 'name'`. Both work now.
- **15 new top-level exports**, including `Skill`, `SubAgentDefinition`, `HookResult`, `PermissionPolicy` and `StrListAttr`. Deep imports still work; the short paths are just no longer missing.

---

## Upgrading to 2.54.0

2.54.0 collapses the system prompt from six rule sections to three and removes the tool-guidance registry. Task authoring, `CmdTask`, `cli`, `Env`, and `Input` are unaffected. Two areas need attention.

### The tool-guidance API is gone

`ToolGuidance` and the four `add_tool_guidance*` methods were removed with no shim, so calls to them raise `AttributeError` / `ImportError` rather than silently doing nothing.

| Before | After |
|---|---|
| `from zrb import ToolGuidance` | *(removed)* |
| `task.add_tool_guidance(ToolGuidance(...))` | put the guidance in the tool's **docstring** |
| `task.add_tool_guidance_factory(lambda ctx: ...)` | `task.prompt_manager.append_prompt(lambda ctx: ...)` |
| `task.add_tool_guidance_section_factory(...)` | `task.prompt_manager.append_prompt(...)` |
| `task.prompt_manager.add_tool_group(name=...)` | *(removed — groups no longer exist)* |
| `task.prompt_manager.tool_names = {...}` | *(removed — nothing filters on it)* |

Per-tool guidance moves into the function's docstring, which pydantic-ai serializes alongside the JSON schema on every request:

```python
def check_stock(warehouse_id: str, sku: str) -> dict:
    """Look up on-hand stock for one SKU in one warehouse.

    Always pass warehouse_id — a lookup without it scans every site and times
    out. An empty result means no stock on hand, not an error.
    """
    ...
```

Cross-cutting policy that is not about one tool is appended after the built-in sections:

```python
task.prompt_manager.append_prompt(
    "## Inventory rules\n- Never quote stock without a warehouse.",
)
```

A block added with `append_prompt` always renders after all built-in sections — there's no positioning control, since it isn't a named section you could place in `ZRB_LLM_INCLUDE_SECTIONS`. If you need it somewhere else in the prompt, put it in a `workflow.md` override instead (see [Programming the Prompt](programming-the-prompt.md)).

### Four prompt sections were retired

`mandate`, `git_mandate`, `journal_mandate`, and `tool_guidance` no longer exist.

| Retired section | Where its content went |
|---|---|
| `mandate` | folded into `workflow` (the Priority Order now opens it) |
| `git_mandate` | enforced by the shell tool policy; the one prompt-side rule moved to `workflow` |
| `journal_mandate` | replaced by the `LogActivity` and `WriteJournalNote` tools |
| `tool_guidance` | tool docstrings, plus a `Tool usage` block in `workflow` |

A pinned `ZRB_LLM_INCLUDE_SECTIONS` or sub-agent `inherit_sections` naming any of them still parses. The name falls through to the custom-section path, so what happens depends on whether a markdown file resolves for it:

- **No override file** — the section composes to `""` and logs a warning at compose time. Nothing crashes; the entry just contributes nothing.
- **You have an override** (`mandate.md` in `ZRB_LLM_PROMPT_DIR`, or `ZRB_LLM_PROMPT_MANDATE`) — it is still emitted, at that position, as a file-backed custom section. Your customization survives untouched.

Either way, update the list to the new defaults:

```bash
export ZRB_LLM_INCLUDE_SECTIONS="persona,workflow,example,system_context,project_context"
```

`ZRB_LLM_INCLUDE_JOURNAL_REMINDER` is removed along with its hook; the journal tools make the reminder unnecessary. `ZRB_LLM_JOURNAL_ENABLED` still works and now unregisters the three journal tools instead of dropping a prompt section.

**Careful with overrides.** If you overrode a retired prompt file (`mandate.md`, `git_mandate.md`, `journal_mandate.md`) *and* you rely on the default section list, your override silently stops being read — the name is no longer in the defaults, so nothing resolves it. Either keep the name in an explicit `ZRB_LLM_INCLUDE_SECTIONS` (it then works as a custom section, see above) or move the content into a `workflow.md` override.

See [ADR-0045](../adr/adr-0045.md) and [ADR-0055](../adr/adr-0055.md) for the reasoning.

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
