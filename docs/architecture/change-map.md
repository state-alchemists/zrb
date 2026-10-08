🔖 [Documentation Home](../README.md) > Architecture > Change Map

# Change Map

For when you already know what you want. The [tier pages](README.md) teach the system in order; this page skips to the file. It is the one to keep open while you work.

## Table of Contents

- [By intent](#by-intent)
- [By symptom](#by-symptom)
- [How to locate anything else](#how-to-locate-anything-else)
- [The tests that pin behaviour](#the-tests-that-pin-behaviour)

## By intent

| I want to… | Open | Then read |
| --- | --- | --- |
| Add a task type | `src/zrb/task/`, subclassing `BaseTask` | [The Task Model](1-spine/task-model.md) |
| Change how inputs, envs or templated values resolve | `src/zrb/input/`, `src/zrb/env/`, `src/zrb/util/attr.py`, `src/zrb/dot_dict/` | [The Task Model](1-spine/task-model.md) |
| Change how a scaffolded project's files are rewritten | `src/zrb/content_transformer/` | [The Task Model](1-spine/task-model.md) |
| Change how a command line finds a task | `src/zrb/group/group.py`, `src/zrb/runner/cli.py` | [The Task Model](1-spine/task-model.md) |
| Change retries, timeout or readiness | `src/zrb/task/base/execution.py` | [Task Execution](1-spine/task-execution.md) |
| Add or rename a tool | `src/zrb/llm/tool/` | [Tools](2-extension-surface/tools.md) |
| Change what the terminal shows | `src/zrb/llm/ui/default/` | [UI](2-extension-surface/ui.md) |
| Change the system prompt or a mandate | `src/zrb/llm/prompt/manager.py` | [Prompts](2-extension-surface/prompts.md) |
| Add a hook point, or change matching | `src/zrb/llm/hook/manager.py` | [Hooks](2-extension-surface/hooks.md) |
| Add a config knob | `src/zrb/config/mixins/` | [Config](2-extension-surface/config.md) |
| Change what a sub-agent inherits | `src/zrb/llm/agent/run/authority_snapshot.py` | [Sub-agents](2-extension-surface/sub-agents.md) |
| Add an HTTP route or a page | `src/zrb/runner/web_route/` | [Web Requests](3-peripheral-flow/web-requests.md) |
| Change what the model may touch | `src/zrb/llm/permission/`, `src/zrb/llm/sandbox/` | [Sandbox Enforcement](3-peripheral-flow/sandbox-enforcement.md) |
| Change the agent loop itself | `src/zrb/llm/agent/run/runner.py` | [The LLM Turn](1-spine/llm-turn.md) |
| Change history persistence or summarization | `src/zrb/llm/history_manager/` | [History & Compaction](3-peripheral-flow/history-and-compaction.md) |
| Change how skills are found or activated, or add a slash command | `src/zrb/llm/skill/`, `src/zrb/llm/custom_command/` | [Skills & Commands](2-extension-surface/skills-and-commands.md) |
| Change how a model name becomes a model, or the rate limits | `src/zrb/llm/config/model_resolver.py`, `src/zrb/llm/config/limiter.py` | [The LLM Turn](1-spine/llm-turn.md) |
| Add a speech or dictation backend | `src/zrb/llm/voice/`, `src/zrb/llm/dictation/backend/`, `src/zrb/llm/speech/backend/` | [Voice on Pipecat](3-peripheral-flow/voice-on-pipecat.md) |

## By symptom

These are the ones whose cause is not where the symptom appears.

| The symptom | What is usually happening | Start at |
| --- | --- | --- |
| A task's action "returns" `None` although it did work | The task has readiness checks, so the action was deferred; the result arrives through `wait_deferred`, not the return value | [Task Execution](1-spine/task-execution.md) |
| Two upstreams ran the same action twice | `mark_as_started` did not precede the first suspension point, so both passed the `is_started` gate | `src/zrb/task/base/execution.py` |
| A successor never runs although the task finished | The successor waits for *ready*, not *completed*, and a readiness check did not pass | [Task Execution](1-spine/task-execution.md) |
| A tool ran without asking | The ruleset answered `allow`, or a higher-priority auto-approve policy did — the approval channel is never consulted for `allow` | [Tool Call & Approval](3-peripheral-flow/tool-call-approval.md) |
| A tool was denied with no prompt shown | A non-interactive run denies an approval-gated call rather than blocking for input | [Tool Call & Approval](3-peripheral-flow/tool-call-approval.md) |
| The model cannot see a file it should | `sandbox_gate` blocked it at the execution chokepoint, which is a separate check from approval | [Sandbox Enforcement](3-peripheral-flow/sandbox-enforcement.md) |
| A tool the model called is not in the tool list | The name resolved differently: check `canonical_tool_name` and `resolve_tools_by_name`, and whether the tool loads eagerly or by name | [Tools](2-extension-surface/tools.md) |
| Nothing appears in the terminal | The run has no UI, or a child run inherited one that buffers instead of printing | [UI](2-extension-surface/ui.md) |
| A `{...}` in a command runs verbatim instead of being filled in | A plain string is a literal; only a `Tpl` is rendered | [The Task Model](1-spine/task-model.md) |
| A task in `zrb_init.py` does not show up as a command | It was declared but never registered, or another task took its alias; zrb prints a diagnostic at startup | [The Task Model](1-spine/task-model.md) |
| A project skill is ignored | Check whether a skill of the same name is found elsewhere, and the `CFG.LLM_SKILLS` allowlist | [Skills & Commands](2-extension-surface/skills-and-commands.md) |
| A hook never fires | The event type did not match, or the hook came from a skill whose frontmatter was not picked up | [Hooks](2-extension-surface/hooks.md) |
| An edited mandate has no effect | The prompt was resolved from a different layer — local prompt dir before packaged files | [Prompts](2-extension-surface/prompts.md) |
| A config value is ignored | The value was read before it was set, or the resolution order picked a different layer | [Config](2-extension-surface/config.md) |
| A sub-agent kept permissions it should not have had | Its authority was snapshotted at delegation time, so a later change does not reach it | [Sub-agents](2-extension-surface/sub-agents.md) |
| A diagram renders as broken boxes in the terminal | It is wider than 120 columns, so the renderer compacted it and then word-wrapped it mid-line | [Architecture](README.md) → *Editing these pages* |

## How to locate anything else

Search patterns that pay off in this codebase, in rough order of usefulness.

| To find | Search |
| --- | --- |
| Who calls a class | `rg -n 'ClassName' src/zrb --glob '*.py'` |
| Where a config knob is read | `rg -n 'NAME_OF_KNOB' src/zrb` |
| A tool's implementation | `rg -n '__name__ = "ToolName"' src/zrb/llm/tool` |
| Which ADR owns a decision | `rg -ln 'the concept' docs/adr/` |
| The test that pins a behaviour | `rg -n 'the behaviour' test/` |
| Where a task type is declared | `rg -n 'class .*BaseTask' src/zrb` |
| Which page documents a module | `rg -ln 'src/zrb/llm/hook' docs/architecture/` |

`AGENTS.md` holds the repository's own map — the package layout and the conventions a change must follow. When this page and `AGENTS.md` disagree, `AGENTS.md` wins, and the disagreement is a bug worth fixing here.

## The tests that pin behaviour

Read the test before changing an area; it is the precise statement of what the code must keep doing.

| Command | What it guards |
| --- | --- |
| `python3 -m pytest test/architecture/ -q` | Every architecture and doc guard: this section's shape, its diagrams, and that every path, name and link it mentions still exists |
| `python3 -m pytest test -q` | Everything; the gate before a commit |
| `./zrb-test.sh` | The repository's full gate, including lint and typing |

## See Also

- [Architecture](README.md) — the tier index and the reading paths
- [The System](0-system/system.md) — the parts and the rules that hold everywhere
- [Architecture, Philosophy & Conventions](../contributing/architecture.md) — why the shape is this shape
- [Framework Conventions](../contributing/framework-conventions.md) — the enforced code rules
- [Where the code lives](../../AGENTS.md) — the repository map

🔖 [Documentation Home](../README.md) > Architecture > Change Map
