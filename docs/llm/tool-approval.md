🔖 [Documentation Home](../README.md) > [LLM](README.md) > Customizing Tool Approval

# Customizing Tool Approval

When the agent wants to run a tool that needs your approval, zrb shows a prompt like this:

```
  🎰 Executing tool 'Bash'
       command: rm -rf build
  ❓ Allow tool Execution? (✅ Y | 🛑 n | 📝 e)?
```

Three ordered lists on `LLMChatTask` control everything about that prompt — whether it appears, what it shows, and what your answer means:

| Stage | Type | Question it answers | Register with |
|---|---|---|---|
| 1. Tool policy | `ToolPolicy` | Should this call skip the prompt (approve or deny it outright)? | `append_tool_policy` / `prepend_tool_policy` / `set_tool_policies` / `remove_tool_policy` |
| 2. Argument formatter | `ArgumentFormatter` | How are the call's arguments displayed? | `append_argument_formatter` / `prepend_argument_formatter` / `set_argument_formatters` / `remove_argument_formatter` |
| 3. Response handler | `ResponseHandler` | What does the typed answer mean? | `append_response_handler` / `prepend_response_handler` / `set_response_handlers` / `remove_response_handler` |

All three also exist as constructor arguments (`tool_policies=`, `argument_formatters=`, `response_handlers=`). The types live in `zrb.llm.tool_call`; `ToolApproved`, `ToolDenied` and `ToolCallPart` in `zrb.llm.agent.types`.

Where these sit relative to permission rules, YOLO and hooks is in [Permission Policy → The Precedence Chain](permission-policy.md#the-precedence-chain): tool policies run at priority 1, before the permission ruleset. To send the prompt somewhere other than the terminal (Telegram, HTTP), use an [approval channel](llm-custom-ui.md#approval-channels) instead.

## Table of Contents

- [Changing how arguments are shown](#changing-how-arguments-are-shown)
- [Skipping the prompt: tool policies](#skipping-the-prompt-tool-policies)
- [Changing what an answer means: response handlers](#changing-what-an-answer-means-response-handlers)
- [Applying it to `zrb llm chat`](#applying-it-to-zrb-llm-chat)
- [Built-ins you can reuse](#built-ins-you-can-reuse)
- [Display settings without code](#display-settings-without-code)

---

## Changing how arguments are shown

An argument formatter receives the UI, the tool call, and the arguments section rendered so far (YAML, indented seven spaces). It returns a replacement string, or `None` to leave it unchanged:

```python
from zrb.llm.tool_call import ArgumentFormatter
from zrb.llm.tool_call.args import parse_tool_args


async def bash_formatter(ui, call, args_section: str) -> str | None:
    if call.tool_name != "Bash":
        return None  # not mine — keep whatever is there
    args = parse_tool_args(call) or {}
    return f"       $ {args.get('command', '')}\n"


chat.append_argument_formatter(bash_formatter)
```

The prompt now reads:

```
  🎰 Executing tool 'Bash'
       $ rm -rf build
  ❓ Allow tool Execution? (✅ Y | 🛑 n | 📝 e)?
```

**Every formatter runs, in list order, and the last non-`None` result wins.** Each one receives the section as the previous formatter left it, so a formatter can also decorate rather than replace (`return args_section + "       ⚠️ destructive\n"`).

> **Order matters for `Write` and `Edit`.** `LLMChatTask` always places its two built-in formatters — `replace_in_file_formatter` (`Edit`) and `write_file_formatter` (`Write`), which render a diff — at the end of the list it is constructed with. A formatter passed to the constructor or added with `prepend_argument_formatter` therefore runs *before* them and is overwritten for those two tools. To change how `Write` or `Edit` is shown, use `append_argument_formatter`, or `set_argument_formatters` to drop the built-ins entirely.

Return the string with its own trailing newline: the instruction line is concatenated straight after it. A formatter that does blocking work (reading a large file, computing a diff) should push it off the event loop with `await asyncio.to_thread(...)`, as the built-ins do, or the TUI freezes while it runs.

## Skipping the prompt: tool policies

A tool policy decides a call before anyone is asked. It returns `ToolApproved()`, `ToolDenied(reason)`, or hands the call on with `await next_handler(ui, call)`:

```python
from zrb.llm.tool_call import auto_approve


async def no_force_push(ui, call, next_handler):
    # lazy: zrb.llm.agent.types loads pydantic_ai
    from zrb.llm.agent.types import ToolDenied
    from zrb.llm.tool_call.args import parse_tool_args

    args = parse_tool_args(call) or {}
    if call.tool_name == "Bash" and "push --force" in args.get("command", ""):
        return ToolDenied(
            "[SYSTEM SUGGESTION]: force-push is not allowed; push a new branch instead."
        )
    return await next_handler(ui, call)


chat.prepend_tool_policy(
    no_force_push,
    auto_approve("Bash", {"command": r"^(git status|git diff|ls)\b"}),
)
```

Policies form a chain: the first to return a verdict decides, and if every policy passes the call on, the prompt is shown. The denial reason reaches the model as the tool result, so make it actionable.

`auto_approve(tool_name, kwargs_patterns)` builds the common case. `kwargs_patterns` maps argument names to regexes, or is a predicate over the argument dict. With a mapping, every named argument must be present in the call and match its regex — a call that omits one is handed on, not approved — while arguments the mapping does not name are ignored; omit it to approve every call to that tool. It never approves a call that asks for `dangerously_skip_sandbox`.

Two limits apply. A [permission-policy](permission-policy.md) `ASK` is a hard ask: a policy's `ToolApproved` is ignored for that call, while its `ToolDenied` still holds. And a permission-policy `DENY` is re-checked at execution time, so a policy cannot approve its way past it.

## Changing what an answer means: response handlers

A response handler receives the typed answer and returns `ToolApproved(...)`, `ToolDenied(reason)`, `None` to show the prompt again, or passes the answer on with `await next_handler(ui, call, response)`:

```python
from zrb.llm.tool_call import auto_approve

always_allowed: set[str] = set()


async def allow_remembered(ui, call, next_handler):
    # lazy: zrb.llm.agent.types loads pydantic_ai
    from zrb.llm.agent.types import ToolApproved

    if call.tool_name in always_allowed:
        return ToolApproved()
    return await next_handler(ui, call)


async def always_for_session(ui, call, response: str, next_handler):
    # lazy: zrb.llm.agent.types loads pydantic_ai
    from zrb.llm.agent.types import ToolApproved

    if response.strip().lower() != "a":
        return await next_handler(ui, call, response)
    always_allowed.add(call.tool_name)
    ui.append_to_output(f"\n  ✅ '{call.tool_name}' approved for this session.")
    return ToolApproved()


chat.prepend_tool_policy(allow_remembered)
chat.prepend_response_handler(always_for_session)
```

Register handlers and policies before the chat starts: the interactive UI takes its copy of the three lists when it is created, so a later `prepend_*` call does not reach a session already running. Mutable state the callables close over, like `always_allowed` above, is the way to change behavior mid-session.

Return `ToolApproved(override_args={...})` to run the call with edited arguments; the model is told its arguments were changed. The interactive UI ends the chain with `default_response_handler`, which handles `y`/`n`/`e` (`e` opens `ZRB_EDITOR` on the arguments) and treats any other text as a denial reason sent back to the model — so prepend your handler, or the default answers first.

When the prompt arrives through the terminal side of an [approval channel](llm-custom-ui.md#approval-channels), only an `e`/`edit` answer reaches the response handlers; `y`, `n` and free text are decided by the channel itself.

The prompt's instruction line (`❓ Allow tool Execution? ...`) is fixed; if you add answers of your own, say so from a formatter.

## Applying it to `zrb llm chat`

The built-in chat task is an ordinary `LLMChatTask`; change it from your `zrb_init.py`:

```python
from zrb.builtin.llm.chat import llm_chat

llm_chat.append_argument_formatter(bash_formatter)
llm_chat.prepend_tool_policy(no_force_push, allow_remembered)
llm_chat.prepend_response_handler(always_for_session)
```

Sub-agents run under the chat's approval handler — its tool policies, argument formatters and response handlers — when they run inside the chat's turn: a `DelegateToAgent` call, and the first turn of a background delegation. A message you send afterwards to a background sub-agent that is still live runs outside any chat turn, so its tool calls skip the chat's tool policies; use a [permission policy](permission-policy.md) for a rule that must bind every sub-agent turn, since that one is carried over.

## Built-ins you can reuse

All importable from `zrb.llm.tool_call` unless noted.

| Name | Kind | What it does | On `llm_chat` by default |
|---|---|---|---|
| `write_file_formatter` | formatter | Shows a diff for `Write` | yes |
| `replace_in_file_formatter` | formatter | Shows a diff for `Edit` | yes |
| `default_response_handler` | response handler | `y` / `n` / `e` / free-text denial | yes (interactive UI) |
| `replace_in_file_response_handler` | response handler | On `e`, opens the `Edit` replacement in `ZRB_DIFF_EDIT_COMMAND` | yes |
| `auto_approve(tool, patterns)` | policy factory | Approves matching calls | yes, for reads inside the project, journal and skill directories |
| `bash_safe_command_policy()` | policy factory | Approves read-only shell commands | yes |
| `read_file_validation_policy` | policy | Denies a `Read` of a missing file | yes |
| `replace_in_file_validation_policy` | policy | Denies an `Edit` whose `old_text` is not in the file. Import from `zrb.llm.tool_call.tool_policy.replace_in_file_validation` | yes |

A tool that *is* the user interaction (like `AskUserQuestion`) can skip approval everywhere with `register_always_auto_approve("ToolName")`, exported from `zrb`.

## Display settings without code

| Variable | Effect |
|---|---|
| `ZRB_LLM_SHOW_TOOL_CALL_DETAIL` | Print tool arguments as calls stream in, not only at the approval prompt |
| `ZRB_LLM_SHOW_TOOL_CALL_RESULT` | Print each tool's raw result |
| `ZRB_EDITOR` | Editor `e` opens on the arguments |
| `ZRB_DIFF_EDIT_COMMAND` | Diff tool `e` opens on an `Edit` replacement |
| `ZRB_LLM_SPEECH_APPROVAL_*` | What is read aloud for an approval when [speech](voice-camera.md) is on |

---

🔖 [Documentation Home](../README.md) > [LLM](README.md) > Customizing Tool Approval
