🔖 [Documentation Home](../README.md) > [Advanced Topics](./) > Upgrading Guide

# Upgrading Guide

What to change in an existing setup when moving to a newer Zrb release. Only the releases that need action are listed — anything not mentioned here is source-compatible.

## Table of Contents

- [Upgrading to 3.16.0](#upgrading-to-3160)
- [Upgrading to 3.15.0](#upgrading-to-3150)
- [Upgrading to 3.14.0](#upgrading-to-3140)
- [Upgrading to 3.12.0](#upgrading-to-3120)
- [Upgrading to 3.11.0](#upgrading-to-3110)
- [Upgrading to 3.10.0](#upgrading-to-3100)
- [Upgrading to 3.8.0](#upgrading-to-380)
- [Upgrading to 3.6.0](#upgrading-to-360)
- [Upgrading to 3.3.0](#upgrading-to-330)
- [Upgrading to 3.2.0](#upgrading-to-320)
- [Upgrading to 3.1.0](#upgrading-to-310)
- [Upgrading to 3.0.0](#upgrading-to-300)
- [Upgrading to 2.54.0](#upgrading-to-2540)
- [Upgrading from 1.x.x to 2.x.x](#upgrading-from-1xx-to-2xx)

---

## Upgrading to 3.16.0

3.16.0 brings an opt-in spoken summary back. Nothing changes unless you set `ZRB_LLM_SPEECH_SUMMARIZE_ABOVE_CHARS`; without it every reply is still read whole.

| Setting | What it does |
|---|---|
| `ZRB_LLM_SPEECH_SUMMARIZE_ABOVE_CHARS` | Replaces the retired `ZRB_LLM_SPEECH_SUMMARIZE`. A reply whose speakable text is longer than this many characters is spoken as a short summary from the small model; `0` (the default) reads every reply whole. The reply is then not streamed, whatever `ZRB_LLM_SPEECH_STREAM` says. |
| `ZRB_LLM_SPEECH_SUMMARY_MODEL` | Active again, no longer retired: the model that writes the summary, used only when the threshold above is set. Empty uses the small model. |
| `ZRB_LLM_SPEECH_SUMMARY_TIMEOUT` | New: seconds the summary may take before the reply is read whole instead (default `15`; `0` is no limit). |

A leftover `ZRB_LLM_SPEECH_SUMMARIZE` is still reported at startup and now names `ZRB_LLM_SPEECH_SUMMARIZE_ABOVE_CHARS`. `ZRB_LLM_SPEECH_MAX_CHARS` and `ZRB_LLM_SPEECH_ON_SCREEN_NOTE` stay retired: a reply is never cut at a fixed length.

---

## Upgrading to 3.15.0

3.15.0 removes the Pipecat input tap that 3.14.0 added behind a flag. It fed every block the microphone captured to a Pipecat pipeline that decided nothing, so that the detector in it could be measured against the boundaries `UtteranceCutter` draws — and that comparison was never the thing that shipped. What shipped is a Pipecat service *behind* the cutter, named by `ZRB_LLM_DICTATION_BACKEND` and `ZRB_LLM_SPEECH_BACKEND`, which does not need the tap.

The setting is reported at startup when it is still set; setting it has no other effect.

| Retired | What to do instead |
|---|---|
| `ZRB_LLM_DICTATION_PIPECAT_ENABLED` | Nothing. Drop it from your environment, `zrb_init.py` and launch scripts. If you wanted a local model, name one: `ZRB_LLM_DICTATION_BACKEND=whisper`, `moonshine` or `funasr`, or `ZRB_LLM_SPEECH_BACKEND=piper` to speak through. Nothing you heard or said changes either way. |

If you were reading the tap's line (`Pipecat input pipeline: 2 speech segment(s), 1.5s of detected speech`) to check a microphone, there is no replacement: `zrb voice mic-test` in `examples/voice-interaction` measures the device against the same threshold dictation uses.

A custom UI built on `BufferedOutputMixin` overrides `send_buffered` (it was `_send_buffered`); rename the method, since there is no alias.

A project or home skill or agent now replaces a built-in one of the same name, as documented — before, the built-in silently won. If you kept a same-named copy only as a stale fork of a built-in, delete it to get the built-in back.

---

## Upgrading to 3.14.0

3.14.0 retires dictation settings about holding zrb's voice and reading back what was heard over it, and four speech settings, which existed to shorten a long reply. Each is reported at startup when it is still set, naming what replaced it; setting one has no other effect.

| Retired | What to do instead |
|---|---|
| `ZRB_LLM_DICTATION_BARGE_IN_ACTION` | Nothing: anything said over zrb steers the turn, and a stop cancels it, so there is no `cancel` left to choose. A stop word said alone (`ZRB_LLM_DICTATION_STOP_WORDS`) still cancels the turn. |
| `ZRB_LLM_DICTATION_TURN_END_TIMEOUT` | Nothing: only `barge_in_action=cancel` waited for a cancelled turn. |
| `ZRB_LLM_DICTATION_ECHO_COOLDOWN` | Nothing: the microphone no longer goes deaf after zrb stops speaking, because room echo outliving playback is what `ZRB_LLM_DICTATION_BARGE_IN_MARGIN` holds speech over zrb against. Speech heard in that moment is judged like any other. |
| `ZRB_LLM_DICTATION_SELF_ECHO_MATCH` | Nothing, and this one is a real loss: the guard that dropped zrb's own words transcribed back is gone. Anything else said over zrb goes to the small model (`ZRB_LLM_DICTATION_INTERRUPT_JUDGE_ENABLED`), which reads what a stop asks but does not drop echo. Lower the playback volume, use headphones, or turn barge-in off. |
| `ZRB_LLM_DICTATION_SELF_ECHO_TAIL` | Nothing — see `_SELF_ECHO_MATCH`. |
| `ZRB_LLM_DICTATION_TRAILING_WORDS` | Nothing: an utterance fed to a streaming transcriber now ends after `ZRB_LLM_DICTATION_MIN_SILENCE` once it has words, without waiting for a word a sentence ends on. Raise `ZRB_LLM_DICTATION_MIN_SILENCE` if you are cut off mid-sentence. |
| `ZRB_LLM_SPEECH_MAX_CHARS` | Nothing: the whole reply is read, so nothing is cut. |
| `ZRB_LLM_SPEECH_SUMMARIZE` | Nothing in 3.14.0; since 3.16.0, `ZRB_LLM_SPEECH_SUMMARIZE_ABOVE_CHARS` — see [Upgrading to 3.16.0](#upgrading-to-3160). |
| `ZRB_LLM_SPEECH_SUMMARY_MODEL` | Nothing in 3.14.0; active again since 3.16.0, used when `ZRB_LLM_SPEECH_SUMMARIZE_ABOVE_CHARS` is set. |
| `ZRB_LLM_SPEECH_ON_SCREEN_NOTE` | Nothing: nothing is left unsaid, so there is nothing on screen to point at. |

`ZRB_LLM_DICTATION_POLITE_WORDS` still exists but no longer applies to stop words: a yes or a no may carry one ("yes please", "no thanks"), a stop may not, so "stop please" is put to the small model instead of matching. Keep `ZRB_LLM_DICTATION_INTERRUPT_JUDGE_ENABLED` on if you relied on that.

---

## Upgrading to 3.12.0

`AnyUI` declares `cancel_current_turn(reason)`, `is_turn_running`, `is_waiting_for_answer` and `is_prompt_answered_since(asked_at)`. A UI built on `BaseUI` or `UIStateDefaultsMixin` already has them. A class that implements `AnyUI` directly must add them, or it fails to instantiate.

---

## Upgrading to 3.11.0

`AnyUI` declares `set_status_badge(key, text)`. `BaseUI`, `MultiUI` and `UIStateDefaultsMixin` implement it; a class that implements `AnyUI` directly must add it.

---

## Upgrading to 3.10.0

3.10.0 moves `/photo` and `/voice` out of the UI into three optional features — camera, dictation and speech — that `zrb llm chat` enables through its public extension points ([Voice and camera](../llm/voice-camera.md)). The commands work as before; configuration, and code that reached into the UI for them, changes.

### Settings

| Before | After |
|---|---|
| `ZRB_LLM_VOICE_ENABLED` | (removed — `/voice` is always offered and explains a missing `zrb[voice]`) |
| `ZRB_LLM_VOICE_MODE` | `ZRB_LLM_DICTATION_BACKEND` |
| `ZRB_LLM_VOICE_PUSH_TO_TALK_KEY` | (removed — `/voice` starts and a pause or `/voice` stops) |
| `ZRB_LLM_VOICE_OPENAI_MODEL` | `ZRB_LLM_DICTATION_OPENAI_MODEL` |
| `ZRB_LLM_VOICE_GOOGLE_MODEL` | `ZRB_LLM_DICTATION_GOOGLE_MODEL` |
| `ZRB_LLM_VOICE_VOSK_MODEL_NAME` | `ZRB_LLM_DICTATION_VOSK_MODEL_NAME` |
| `ZRB_LLM_VOICE_VOSK_MODEL_URL` | `ZRB_LLM_DICTATION_VOSK_MODEL_URL` |
| `ZRB_LLM_UI_COMMAND_VOICE` | `ZRB_LLM_DICTATION_COMMANDS` |
| `ZRB_LLM_UI_COMMAND_PHOTO` | `ZRB_LLM_CAMERA_COMMANDS` |

There are no aliases: an old variable is ignored, and from 3.12.0 zrb says so when it starts, naming what to set instead. Each command in `ZRB_LLM_CAMERA_COMMANDS`, `ZRB_LLM_DICTATION_COMMANDS` and `ZRB_LLM_SPEECH_COMMANDS` must start with `/` and is matched case-sensitively: `photo` or `/Photo` never matches `/photo`. New settings are listed in [LLM configuration § 21](../configuration/llm-config.md#21-voice-and-camera).

### Code

| Before | After |
|---|---|
| `ActionCommand("/x", lambda kwargs: ...)` | `ActionCommand("/x", lambda kwargs, ui: ...)` — the action also gets the chat UI, or `None` |
| `AnyCustomCommand.handle(self, kwargs)` | `handle(self, kwargs, ui)` |
| `run_custom_command(message, commands)` | `run_custom_command(message, commands, ui)` |
| `from zrb.llm.voice import VoiceEngine` | `zrb.llm.dictation`: `record(should_record)` / `listen(config, should_listen)` for audio, `zrb.llm.dictation.backend.get_dictation_backend(...).transcribe(audio)` for text |
| `from zrb.llm.util.camera import get_camera_photo` | `from zrb.llm.camera import AutoCameraBackend`; `await AutoCameraBackend().capture(device)` |
| `missing_tool_hint()` (camera) | `backend.get_failure_hint()` on the backend that captured |
| `ui.voice`, `ui.voice_commands`, `ui.photo_commands`, `ui.handle_toggle_voice`, `ui.handle_photo_command`, `ui.submit_photo` | (removed) |
| `UIConfig(voice_commands=..., photo_commands=...)` | `DictationConfig(commands=...)`, `CameraConfig(commands=...)` passed to `enable_dictation`/`enable_camera` |

A custom `LLMChatTask` gets the features with `enable_camera(task)`, `enable_dictation(task)` and `enable_speech(task)`.

---

## Upgrading to 3.8.0

Only code that reads snapshot progress or restores snapshots directly is affected.

| Before | After |
|---|---|
| `SnapshotProgress.copied` | (removed — nothing is copied any more). Read `event.stage`, `event.skipped`, `event.reason` by name; unpacking the event by position fails |
| `await manager.restore_snapshot(sha)` returns `bool` | returns `RestoreOutcome(restored, left_behind)`, truthy exactly when the restore ran, so `if await manager.restore_snapshot(sha):` still works |

---

## Upgrading to 3.6.0

| Before | After |
|---|---|
| `task.cli_only` | `task.is_cli_only` (the `cli_only=` constructor keyword is unchanged) |

`AnyUI` gained seven members, and `last_output`, `snapshot_manager` and `history_manager` are read-only in the contract. A UI built on `BaseUI` or the mixin is unaffected; a class that implements `AnyUI` directly must add them, and one that assigns `self.last_output = ...` must declare its own setter.

---

## Upgrading to 3.3.0

3.3.0 replaces thirteen flattened state accessors on `BaseUI` with the four
objects that already held the state. Only a UI that subclasses `BaseUI` and
reads or writes these names is affected: `AnyUI` is unchanged, and so are
`SimpleUI` and `EventDrivenUI`, the two levels the [custom UI
guide](../llm/llm-custom-ui.md) recommends. Every removal fails loudly with
`AttributeError`, so a green run means you are done.

### `BaseUI` state lives on its parts

| Before | After |
|---|---|
| `ui.current_confirmation` | `ui.confirmation.current` |
| `ui.confirmation_queue` | `ui.confirmation.queue` |
| `ui.confirmation_output_buffer` | `ui.confirmation.output_buffer` |
| `ui.voice_mode_active`, `ui.voice_recording_active`, `ui.voice_stop_event`, `ui.voice_task` | `ui.voice.*` in 3.3.0; removed in 3.10.0 ([above](#upgrading-to-3100)) |
| `ui.active_subagent_persona` | `ui.persona.active_subagent` |
| `ui.original_persona_snapshot` | `ui.persona.original_snapshot` |
| `ui.session_token_usage` | `ui.usage.session_token_usage` |
| `ui.session_cache_read_tokens` | `ui.usage.session_cache_read_tokens` |
| `ui.context_tokens` | `ui.usage.context_tokens` |
| `ui.reset_session_token_usage()` | `ui.usage.reset()` |

Each was a getter (and often a setter) whose whole body reached one field on
one part, so the part is the shorter name for the same state. Reads and writes
both move with it — `ui.confirmation.current = future` replaces
`ui.current_confirmation = future`. The token counters under `ui.usage` are
read-only and updated through `ui.usage.accumulate(...)`.

`accumulate_usage` is deliberately not in the table. It stays a method on
`BaseUI` because the custom UI guide lists it as an enrichment hook and
`MultiUI`/`BufferedUI` implement it too.

A UI that tolerates hosts other than `BaseUI` should reach the part, not the
field: `getattr(ui, "usage", None)` in place of
`getattr(ui, "session_token_usage", 0)`. `StdUI` and `MultiUI` keep none of
this state, exactly as before.

---

## Upgrading to 3.2.0

The fourteen stateless data utilities moved under one `util` group. Only the CLI path changes; the `from zrb.builtin import ...` names are the same.

| Before | After |
|---|---|
| `zrb base64 encode`, `zrb md5 hash`, `zrb uuid ...`, … | `zrb util base64 encode`, `zrb util md5 hash`, `zrb util uuid ...`, … |

The moved groups are `base64`, `case`, `cron`, `hash`, `hex`, `json`, `jwt`, `md5`, `number`, `random`, `time`, `ulid`, `url` and `uuid`. Update scripts and CI steps that call them.

---

## Upgrading to 3.1.0

- **Readiness checks are capped.** A readiness check that never succeeds now fails its task after `ZRB_TASK_READINESS_TIMEOUT` (default `60000` ms) instead of hanging. Set it to `0`, or pass `readiness_timeout=0`, to restore the unbounded wait.
- **`zrb server start` refuses an unsecured public bind.** Binding beyond loopback exits with an error when web auth is off or `ZRB_WEB_SUPER_ADMIN_PASSWORD` / `ZRB_WEB_SECRET_KEY` still hold their defaults. Enable auth with your own credentials, or bind to `127.0.0.1`. There is no override flag.

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
from zrb.llm.ui import UIConfig

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
| `class MyUI(UIProtocol):` | `class MyUI(AnyUI):` (or subclass `BaseUI`/`SimpleUI`/`EventDrivenUI`, which already do) |
| `class MyChannel(ApprovalChannel):` | `class MyChannel(AnyApprovalChannel):` |

If you only use the built-in `llm_chat` task and never subclassed these directly, no change is needed — every built-in UI and approval channel already inherits the new base.

### Worth knowing (no action needed)

- **`CFG` assignments now fail fast.** An unknown `CFG.UPPERCASE` name raises `AttributeError` naming the closest real knob; a value the field can't accept raises `ValueError` at the assignment site. This only surfaces bugs that were previously silent no-ops.
- **A broken `zrb_init.py` is reported precisely, not hidden — and still not fatal by default at a terminal.** The file, line, and exception type now print to stderr; the CLI still starts with whatever partial state resulted, same as before. `ZRB_INIT_STRICT` makes it fatal instead, and since 3.5.0 it defaults to `auto`, which is on wherever stderr is not a terminal (CI, cron, piped runs) — see [CI/CD Integration](ci-cd.md#zrb_init_strict-already-covers-you-here).
- **13 internal `raise Exception(...)` sites now raise typed errors** (`SearchToolError`, `RuntimeError`, `ValueError`) — a bare `except Exception` still catches them.
- **6 config mixin classes were renamed** (`ConfigLLMContent` → `LLMContentMixin`, etc.) — only relevant if you imported one directly from `zrb.config.mixins`.

### Coming from before 2.58.0

These changes first shipped in 2.58.0; skip to [Rendering is opt-in](#rendering-is-opt-in-300b5) if you are already on 2.58.0 or later. Three changes need action. All fail loudly — `AttributeError`, `TypeError`, or `ImportError` — rather than silently doing the wrong thing, so a green test run means you are done. Env vars and prompt files are unaffected.

#### `add_X` on ordered collections is `append_X` or `prepend_X`

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

#### Task constructors are keyword-only after `name`

```python
Task("build")                 # still fine
Task(name="build", color=5)   # still fine
Task("build", 5)              # TypeError
```

Applies to `Task`, `CmdTask`, `LLMTask`, `LLMChatTask`, `RsyncTask`, `Scaffolder`, `Scheduler`, `HttpCheck`, `TcpCheck`, `BaseTrigger`, `BaseTask` and `make_task`. `LLMChatTask` had 73 positionally-passable parameters, so any future insertion would otherwise have been a silent breaking change.

#### Two renames

| Before | After |
|---|---|
| `RsyncTask(auto_render_shell=...)` | `RsyncTask(render_shell=...)` — then removed entirely in 3.0.0b5, see below |
| `from zrb import AnyAttr` | `from typing import Any`, or the specific `StrAttr` / `BoolAttr` / … |

`AnyAttr` was defined as `Any \| fstring \| Callable[..., Any]`, which collapses to plain `Any` — it constrained nothing while looking like it did.

#### Rendering is opt-in (3.0.0b5)

A bare `str` attribute is now a **literal**. Wrap a template in `Tpl` to have it rendered against the context:

```python
CmdTask(cmd="echo '{literal}'")               # runs verbatim — no flag needed
CmdTask(cmd=Tpl("echo {ctx.input.name}"))     # rendered
```

Every `render_*` / `auto_render` parameter is gone — they existed only to opt *out* of the old implicit rendering, which no longer happens. Drop `render_x=False` from a call that wanted a literal; wrap the string in `Tpl` where you wanted a template. `fstring` (which was `= str`) is removed from `zrb.__all__`; `Tpl` replaces it.

#### Worth knowing (no action needed, from 2.58.0)

- **`py.typed` ships**, so `mypy`/`pyright` now actually check your zrb usage. Expect to see real errors the first time — they were always there, just invisible.
- **Collections accept any `Sequence`.** `upstream=(a, b)` and `a >> (b, c)` used to store the tuple as if it were a task and fail later with `'tuple' object has no attribute 'name'`. Both work now.
- **18 new top-level exports**, including `Skill`, `SubAgentDefinition`, `HookResult`, `PermissionPolicy` and `StrListAttr`. Deep imports still work; the short paths are just no longer missing.

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

A block added with `append_prompt` always renders after all built-in sections — there's no positioning control, since it isn't a named section you could place in `ZRB_LLM_INCLUDE_SECTIONS`. If you need it somewhere else in the prompt, put it in a `workflow.md` override instead (see [Programming the Prompt](../llm/programming-the-prompt.md)).

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

Either way, update the list to the current defaults:

```bash
export ZRB_LLM_INCLUDE_SECTIONS="persona,principle,workflow,example,profile,system_context,project_context"
```

`ZRB_LLM_INCLUDE_JOURNAL_REMINDER` is removed along with its hook; the journal tools make the reminder unnecessary. `ZRB_LLM_JOURNAL_ENABLED` still works and now unregisters the journal tools instead of dropping a prompt section.

**Careful with overrides.** If you overrode a retired prompt file (`mandate.md`, `git_mandate.md`, `journal_mandate.md`) *and* you rely on the default section list, your override silently stops being read — the name is no longer in the defaults, so nothing resolves it. Either keep the name in an explicit `ZRB_LLM_INCLUDE_SECTIONS` (it then works as a custom section, see above) or move the content into a `workflow.md` override.

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
| `from zrb.llm.app import PollingUI` | `from zrb.llm.ui import PollingUI` (removed in 3.0.0 — use `EventDrivenUI`) |

If you only interact with the built-in `llm_chat` task (i.e. you don't subclass or import UI classes directly), no change is needed.

### Hooks Timeout Unit

`ZRB_HOOKS_TIMEOUT` changed from **seconds** to **milliseconds** in 2.20.0.

| 1.x.x | 2.x.x |
|---|---|
| `ZRB_HOOKS_TIMEOUT=30` (30 seconds) | `ZRB_HOOKS_TIMEOUT=30000` (30 seconds) |

Update your environment variable if you had set a custom timeout.

The 2.x line also added features that need no migration (multiple UIs, approval channels, rewind, MCP, worktrees, …); they are listed per release in the [changelog](../changelog/README.md).

🔖 [Documentation Home](../README.md) > [Advanced Topics](./) > Upgrading Guide
