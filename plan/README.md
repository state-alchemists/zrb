🔖 [Documentation Home](../README.md)

# Plan: converge zrb on its own conventions

**Status:** proposed, not started
**Baseline:** `2.69.0`, commit `ae15e58c6`, measured 2026-09-02

---

## 1. What was measured

| Metric | Value |
| --- | --- |
| Python files / lines in `src/zrb` | 438 / 71,378 |
| Of which `src/zrb/llm/` | 241 / 49,618 (**70%**) |
| `import zrb` wall time | 203 ms |
| `CFG` public knobs | 240 (234 via one `EnvField` descriptor, 1 hand-written property) |
| ADRs | 90 |
| `LLMChatTask.__init__` parameters | **73** (50 shared with `LLMTask`, in a different order) |
| `LLMTask.__init__` parameters | **52** |
| `LLMChatTask` public properties | ~70, of which **8** are settable |
| `LLMChatTask` public methods | 39 |
| `BaseUI` methods / lines | **139 / 1,409** |
| `UIProtocol` methods | 6 |
| Architecture ratchet tests | 6 (`test/architecture/`) |

Commands used are recorded in each phase file so the numbers can be re-measured.

## 2. Verdict on the goal

**The goal makes sense and is achievable — but it is a convergence job, not a redesign.**

The design you describe is already written down. ADR-0090 (registries, managers,
layered resolution), ADR-0091 (three channels, five families, one mutation
surface) and `docs/configuration/llm-collections.md` state exactly the model in
the goal, including deferred evaluation. The config layer already lives it: 234
of 240 knobs are one descriptor with one behavior. `test/architecture/` already
proves the project knows how to make a convention *enforced* rather than
aspirational.

What is missing is faithfulness. Nine specific, enumerable places where the code
does not do what the ADRs say — listed in §3. Every one is a bounded diff. None
requires a new abstraction.

### Three pushbacks

**(a) "Everything has to be configurable" is the cause of the biggest problem, not the cure.**
`LLMChatTask.__init__` has 73 parameters. That *is* what "everything configurable"
looks like when each new feature earns a constructor argument. Nobody guesses 73
parameters right, and the two task classes have already drifted: they share 50
parameters in a **different order**, `LLMTask` alone has `dynamic_yolo` and
`summarize_commands`, `LLMChatTask` alone has 25 UI parameters. The goal has to be
restated as **one uniform way per component family** — five registries, five
managers, one verb set — *not* a parameter per feature. Phase 5 restates it that
way. If you actually want all 73 kept as constructor arguments, say so and I will
drop Phase 5; the rest of the plan stands either way.

**(b) Your own example does not work today.**
`llm_chat.prompt_manager = prompt_manager` raises `AttributeError` —
`prompt_manager` is a read-only property. 8 of ~70 properties are settable and the
set is arbitrary: `readiness_failure_threshold` is settable, `retries` is not;
`ui_factories` is settable, `tools` is not. Phase 4 fixes this, and it is the
phase closest to the stated goal.

**(c) "Framework-wide" work is really LLM-subsystem work.**
70% of the code is under `llm/`. Phases 3–8 touch almost nothing else. Worth
naming so the effort estimate is honest.

## 3. The gap, measured

| # | Gap | Evidence | Phase |
| --- | --- | --- | --- |
| G1 | Config typos are a silent no-op | `CFG.LLM_MODELL = "oops"` succeeds | 1 |
| G2 | Config type errors surface far from the cause | `CFG.LLM_MAX_REQUESTS_PER_MINUTE = "not-a-number"` succeeds; blows up on next read | 1 |
| G3 | Two `CFG` reads happen at import time, so `zrb_init.py` cannot change them | `builtin/todo.py:40`, `builtin/searxng/start.py:49` | 2 |
| G4 | `zrb_init.py` failures are swallowed | `__main__.py` `except BaseException: print(...)`, no file/line, execution continues with half-applied config | 2 |
| G5 | Task mutation surface violates ADR-0091 Part 2 | `append_tool` with no `set_tools`/`remove_tool`; `prepend_tool_policy` with no append/set/remove; `set_history_manager` **and** a settable `history_manager` property | 3 |
| G6 | Hook family uses its own verbs | `HookRegistry.register` (not `add_hook`), `clear_manual` (skills/agents use `clear_discovered`), `HookManager.search_dirs` property **and** `get_search_directories()` | 3 |
| G7 | Components are not swappable | 8 of ~70 properties settable, arbitrarily chosen | 4 |
| G8 | Constructor surface unguessable | 73 / 52 params, 50 shared but reordered, silently divergent | 5 |
| G15 | Two UI configuration paths that disagree | `UIConfig` (used by `SimpleUI`/web/Telegram) defaults exit commands to `["/exit", "/quit"]`; `CFG.DEFAULT_LLM_UI_COMMAND_EXIT` (used by the TUI) is `"/q, :q, /bye, /quit, /exit"`. `ZRB_LLM_UI_COMMAND_EXIT` only affects one of them | 5 |
| G9 | Two config objects | `CFG` and `llm_config`; `llm_config.model` reads `CFG.LLM_MODEL` then falls back to a hardcoded `"openai-chat:gpt-4o"` | 6 |
| G10 | Prompt family has two registries | public `prompt_registry` **and** private `_ProviderRegistry` in `prompt/manager.py`, which ADR-0090 already flagged as ad-hoc | 7 |
| G11 | `SubAgentManager` does two jobs | roster (`add_agent`…) **and** construction (`create_agent`, `create_llm_chat_task`, `resolve_agent_build`), 482 lines | 7 |
| G12 | The UI contract is misnamed, misplaced, and misdocumented | It is called `UIProtocol`, not `AnyUI`, breaking a 13-for-13 convention; it lives in `llm/tool_call/` though it types the `ui` slot on every task; `ui/__init__.py` promises 4 methods where there are 6 | 8 |
| G13 | 13 `raise Exception`, plus 4 error messages with no context | `llm/tool/search/*` (12), `builtin/changelog.py:104`; `"No UI available"`, `"No subtree config found"` ×2, `"Invalid priority format"` | 9 |
| G14 | Config mixin names use two conventions | `FoundationMixin`/`WebMixin` (12) vs `ConfigLLMContent`/`ConfigCLIStyle` (8) | 9 |
| G16 | No single answer to "which pattern do I use?" | 10 orthogonal patterns (13 `Any*`, 16 Mixins, 18 parts, 12 registries, 15 managers, 15 `ContextVar`s, 7 `*Attr`, 7 `Capability`, 4 lazy categories, 239 `EnvField`s) documented across 90 ADRs and 41 pages, with no lookup table | 0 |
| G17 | The ADR log drifted into walls of prose | Average paragraph tripled: 226 chars (ADR-0001–0030) → 615 (ADR-0061–0091); **125 of 627 paragraphs exceed 700 chars**, worst is 4,357; six files hold a third of them | 10 |
| G18 | Four ADR "Where it lives" paths no longer exist | `llm/agent/tool_result.py`, `llm/app/layout.py`, `llm/task/chat/building.py` (plus `zrb_init.py`, which is correctly cited as a user file) | 10 |

## 4. Phases

Ordered by value per unit of risk. Each phase is independently shippable, ends
with a green `./zrb-test.sh`, and leaves behind a ratchet test so the gap cannot
reopen. **Execute in order** — later phases assume earlier ones landed.

| Phase | File | Theme | Risk | Est. |
| --- | --- | --- | --- | --- |
| 0 | [`00-conventions.md`](00-conventions.md) | The rulebook (R1–R12) **and** the one-page "which pattern do I reach for?" table. Read first, write no code. | none | 1 d |
| 1 | [`01-config-safety.md`](01-config-safety.md) | Typos and type errors fail loudly, at the cause | low | 1 d |
| 2 | [`02-deferred-evaluation.md`](02-deferred-evaluation.md) | No `CFG` read at import time; `zrb_init.py` errors are loud | low | 1 d |
| 3 | [`03-uniform-mutation-surface.md`](03-uniform-mutation-surface.md) | One verb set across all five families and both task classes | medium | 3 d |
| 4 | [`04-swappable-slots.md`](04-swappable-slots.md) | `llm_chat.prompt_manager = pm` works, and so does every sibling | medium | 2 d |
| 5 | [`05-constructor-surface.md`](05-constructor-surface.md) | 73 params → a guessable core; the two UI config paths stop disagreeing | high | 4 d |
| 6 | [`06-one-llm-config.md`](06-one-llm-config.md) | Retire `llm_config` into `CFG` + a model resolver | medium | 2 d |
| 7 | [`07-registry-hygiene.md`](07-registry-hygiene.md) | Kill `_ProviderRegistry`; split `SubAgentManager` | medium | 2 d |
| 8 | [`08-ui-contract.md`](08-ui-contract.md) | `AnyUI`, in the package that owns it, documented truthfully | low | 1.5 d |
| 9 | [`09-error-and-naming.md`](09-error-and-naming.md) | Typed errors, one mixin naming convention | low | 1 d |
| 10 | [`10-adr-and-docs-readability.md`](10-adr-and-docs-readability.md) | Reflow 125 wall-of-text ADR paragraphs; fix 3 stale citations; 3 missing TOCs; a density ratchet | none | 2 d |

Phases 1, 2, 8 and 9 are safe to ship in any order and give the fastest visible
return. **Phase 5 is the only one that needs a decision from you before starting**
(three options, §0 of that file); everything else has a single recommended path.

Total: ~20.5 days sequential. Phases 1+2+9 alone (3 days) close the two
silent-failure classes and are worth shipping regardless of what happens to the
rest. **Phase 0 and Phase 10 together (3 days, zero code) are the whole
onboarding story** — the decision table and the ADR reflow — and can be done by
someone who is not ready to touch `llm/` yet.

**One correction the investigation forced:** Phase 8 was scoped as a 4-day UI
refactor on the assumption the UI was hard to swap. It is not — `llm/ui/__init__.py`
documents a five-level ladder where the entry point needs 2 methods, and
`docs/advanced-topics/llm-custom-ui.md` is a 1,000-line guide. Phase 8 is now a
1.5-day naming and documentation fix, and §0 of that file explains the change.
The four days saved are better spent on Phase 5.

## 5. What this plan deliberately does not do

- **No new abstraction layer.** ADR-0090/0091 already name every concept needed.
  Nothing here adds a plugin system, a DI container, or a config schema language.
- **No performance work.** 203 ms `import zrb` is fine, and the lazy-import
  discipline is already enforced by `test/architecture/test_lazy_import_categories.py`.
  One eager-load observation is recorded in Phase 2 §5 as a note, not a task.
- **No test-suite speed work.** `./zrb-test.sh` takes ~92 s; you have deferred it.
- **No back-compat shims.** Renames are clean breaks with a changelog entry, per
  project convention.
- **No docs rewrite.** Measured: the user-facing docs average 154–228 characters
  per paragraph, carry 21–32 code blocks per page, and 26 of the 29 pages over
  150 lines already have a table of contents. They are in good shape. Phase 10
  reflows the **ADR log** (a different, measured problem) and adds the three
  missing TOCs; every other phase amends only the lines its own change
  invalidates.
- **No ADR splitting or renumbering.** Three records carry more than one decision
  and are over-long because of it. Phase 10 reflows them in place and flags them;
  splitting changes every cross-reference and is a content decision, not a
  formatting one.

## 6. Definition of done for the whole plan

1. `./zrb-test.sh` green, coverage ≥ 90%.
2. Every gap G1–G18 has a ratchet test in `test/architecture/` that fails if it
   reopens.
3. `docs/configuration/llm-collections.md` describes the code with no
   "hooks are the exception" caveats.
4. This works, verbatim, in a `zrb_init.py`:

```python
from zrb import CFG, prompt_registry, skill_registry, tool_registry
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.registry import PromptRegistry

CFG.LLM_MODEL = "anthropic:claude-opus-5"      # scalar, env-backed
CFG.LLM_MODELL = "typo"                        # -> AttributeError, names the typo

prompt_registry.append_prompt("Always cite file paths.")          # delta on the default
tool_registry.append_tool(my_tool)                                # delta on the default
skill_registry.add_skill(my_skill)                                # keyed add

llm_chat.prompt_manager = PromptManager(registry=PromptRegistry())  # wholesale swap
llm_chat.set_tools([my_tool])                                       # wholesale swap
```

🔖 [Documentation Home](../README.md)
