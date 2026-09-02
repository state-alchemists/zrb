🔖 [Plan](README.md)

# Phase 3 — One verb set, everywhere

Enforces **R5**, **R6**, **R7**. Risk: medium. Estimate: 3 days.

Clean breaks, no shims — project convention. Every rename gets a changelog entry.

## The inventory

Re-derive it before starting:

```bash
cd /home/gofrendi/zrb
python - <<'EOF'
import inspect
from zrb.builtin.llm.chat import llm_chat
t = type(llm_chat)
meths = sorted(n for n, _ in inspect.getmembers(t, inspect.isfunction) if not n.startswith('_'))
props = inspect.getmembers(t, lambda o: isinstance(o, property))
print("VERBS:", [m for m in meths if m.split('_')[0] in ('append','prepend','set','add','remove')])
print()
print("SETTABLE PROPS:", sorted(n for n, v in props if v.fset))
EOF
```

Measured baseline (2.69.0). Every row is a rule violation:

| Collection on `LLMChatTask` | Has | Missing | Rule |
| --- | --- | --- | --- |
| tools | `append_tool` | `prepend_tool`, `set_tools`, `remove_tool` | R5 |
| tool factories | `append_tool_factory` | `prepend_`, `set_`, `remove_` | R5 |
| toolsets | `append_toolset` | `prepend_`, `set_`, `remove_` | R5 |
| toolset factories | `append_toolset_factory` | `prepend_`, `set_`, `remove_` | R5 |
| history processors | `append_history_processor` | `prepend_`, `set_`, `remove_` | R5 |
| triggers | `append_trigger` | `prepend_`, `set_`, `remove_` | R5 |
| custom commands | `append_custom_command` | `prepend_`, `set_`, `remove_` | R5 |
| hook factories | `append_hook_factory` | `prepend_`, `set_`, `remove_` | R5 |
| tool policies | `prepend_tool_policy` **only** | `append_`, `set_`, `remove_` | R5 |
| response handlers | `prepend_response_handler` **only** | `append_`, `set_`, `remove_` | R5 |
| argument formatters | `prepend_argument_formatter` **only** | `append_`, `set_`, `remove_` | R5 |
| UIs | `append_ui`, `set_ui` | `prepend_ui`, `remove_ui` | R5 |
| UI factories | `append_ui_factory`, `set_ui_factory` **and** a settable `ui_factories` property | one name, plus `prepend_`/`remove_` | R5, **R7** |
| approval channels | `append_approval_channel`, `set_approval_channel` **and** a settable `approval_channels` property | one name, plus `prepend_`/`remove_` | R5, **R7** |
| history manager | `set_history_manager` **and** a settable `history_manager` property | one name | **R7** |

Two more, on the hook family:

| Site | Problem | Rule |
| --- | --- | --- |
| `llm/hook/registry.py:46` | `register(...)` where every sibling family uses `add_X` | R6 |
| `llm/hook/registry.py:114` | `clear_manual()` clears *everything*, not just manual entries — the name lies | R6 |
| `llm/hook/manager.py:128` `search_dirs` property **and** `:610` `get_search_directories()` | two names for one concept | **R7** |
| `llm/skill/manager.py:179` `get_search_directories()` vs `llm/agent/subagent/manager.py:110` `root_dir` property | three families, three spellings | **R7** |

## Step 3.1 — Pick the canonical spelling (do this first, once)

Decide and write into `docs/advanced-topics/framework-conventions.md`:

- **Search directories:** a settable property named `search_dirs` on every
  manager. Delete `get_search_directories()` (22 src / 72 test / 4 doc call
  sites) and `SubAgentManager.root_dir` (a *different* concept — the scan root —
  so keep it, but rename to `scan_root` so it cannot be confused with
  `search_dirs`; confirm by reading `subagent/manager.py:109-117` that it is
  indeed the scan root and not a search dir).
- **Component slot:** a settable property, not a `set_X()` method, when the
  collection holds exactly one thing (`history_manager`, `prompt_manager`).
  `set_X()` survives only for *collections*, where it means "replace the whole
  list" (ADR-0090 Part 2). So `set_history_manager` is deleted in favor of the
  property; `set_tools` is added.

Both choices are R7-driven: one concept, one name.

## Step 3.2 — Fill in the ordered-collection verbs (R5)

For each of the 15 rows in the first table, in `src/zrb/llm/task/chat/task.py`
and `src/zrb/llm/task/llm_task.py`:

The task classes are facades over composed parts (`LLMTaskBuilding` and friends,
per ADR-0035). **Add the real implementation on the part, then a one-line
delegator on the task.** Find the owning part first:

```bash
grep -n "append_tool\|append_history_processor\|prepend_tool_policy" \
  src/zrb/llm/task/*.py src/zrb/llm/task/chat/*.py
```

Template — for the ordered collection `X` on part `P`:

```python
# on the part
def append_x(self, *items: XType) -> None:
    """Add *items* to the end of the pipeline."""
    self._x.extend(items)

def prepend_x(self, *items: XType) -> None:
    """Add *items* to the front of the pipeline."""
    self._x[0:0] = items

def set_xs(self, items: Sequence[XType]) -> None:
    """Replace the whole pipeline — ignores the layer below (ADR-0090 Part 2)."""
    self._x = list(items)

def remove_x(self, item: XType) -> None:
    """Drop the first entry equal (or identical) to *item*."""
    for index, existing in enumerate(self._x):
        if existing is item or existing == item:
            del self._x[index]
            return
```

```python
# on the task — one line each, no logic
def append_x(self, *items: XType) -> None:
    self._base_building.append_x(*items)
```

Notes that matter:

- **Plurality.** `set_` takes the plural (`set_tools`, `set_tool_policies`);
  `append_`/`prepend_`/`remove_` take the singular. This is the shape
  `ToolRegistry` and `PromptRegistry` already use — match them exactly, do not
  invent a third.
- **`remove_x` on a not-present item is a no-op, not an error.** That is what
  `PromptDelta.apply` in `llm/prompt/registry.py:56` already does; be consistent.
- **`llm/task/llm_task.py` and `llm/task/chat/task.py` are both under a facade
  size budget** (900 lines each, `test/architecture/test_facade_size_budget.py`).
  Adding ~45 delegators will blow it. That is a signal, not an obstacle: the
  delegators belong in the part files, and if the budget is still exceeded, bump
  it **in the same diff with a one-line reason** as the test's own comment
  instructs. Do not bump it reflexively — first check whether the delegators can
  live on a shared base both task classes already inherit.
- **Do not add `add_x` aliases.** R5 forbids them; `ToolRegistry` and
  `PromptRegistry` already omit them.

## Step 3.3 — Resolve the R7 duplicates

Three concepts, each currently reachable two ways. Delete one of each:

| Keep | Delete | Call sites to update |
| --- | --- | --- |
| `history_manager` property (settable) | `set_history_manager()` | src 2, test 8, docs 1 |
| `approval_channels` property (settable) | `set_approval_channel()` | src 7, test 10, docs 4 |
| `ui_factories` property (settable) | `set_ui_factory()` | src 6, test 4, docs 13 |
| `search_dirs` property (settable) | `get_search_directories()` | src 22, test 72, docs 4 |

For each: `grep -rn "<old_name>" src test docs` and update every hit. The
`get_search_directories` rename is the big one (98 sites) — do it as its own
commit so the diff stays reviewable, and note that `search_dirs` already appears
75/142 times, so most sites are already spelled the target way.

Watch out on `set_ui_factory` → the property is plural (`ui_factories`) while the
method was singular. Read each of the 6 src call sites: a caller passing one
factory must become `ui_factories = [factory]`, not `ui_factories = factory`.

## Step 3.4 — Fix the hook family verbs (R6)

`src/zrb/llm/hook/registry.py` and `src/zrb/llm/hook/manager.py`:

- `register(...)` → `add_hook(...)`. 12 src / 76 test / 10 doc sites for
  `.register(` — but that grep also matches unrelated `.register(` calls, so
  filter to the hook ones:
  `grep -rn "hook_registry.register\|hook_manager.register\|self._registry.register" src test docs`
- `clear_manual()` → `clear()`. Only 2 src sites, 0 tests. Update the docstring:
  it drops the entire collection, so the name must say that.
- `HookManager.register` → `add_hook` (the manager delegator).

**Hooks stay event-keyed, and that is fine.** A hook declares its own event, so
the key is a property of the value. What R6 requires is the *verb set*
(`add_hook`/`set_hooks`/`remove_hook`), not a name-keyed dict. Phase 0.3 already
amended ADR-0091 to say exactly this — confirm that amendment landed before
starting, or the code change reads as an ADR violation.

Also update `docs/configuration/llm-collections.md`: the "Hooks are neither…
`register`" paragraph and the hooks row of the families table both become
`add_hook` / `set_hooks(event, hooks)` / `remove_hook`.

## Step 3.5 — Ratchet: the verb set is uniform (R5, R6, R7)

New file `test/architecture/test_mutation_surface.py`. Same shape as the other
architecture tests (`REPO_ROOT`/`SRC`, collect-then-assert).

Three tests, each importing the real objects rather than parsing source
(these are public APIs; `inspect` is the right tool):

```python
ORDERED_COLLECTIONS = {
    # host import path -> stem, plural
    "zrb.llm.tool.registry:tool_registry": [("tool", "tools"),
                                            ("tool_factory", "tool_factories"),
                                            ("toolset_factory", "toolset_factories")],
    "zrb.llm.prompt.registry:prompt_registry": [("prompt", "prompts")],
    "zrb.builtin.llm.chat:llm_chat": [("tool", "tools"), ("toolset", "toolsets"),
                                      ("history_processor", "history_processors"),
                                      ("trigger", "triggers"),
                                      ("custom_command", "custom_commands"),
                                      ("tool_policy", "tool_policies"),
                                      ("response_handler", "response_handlers"),
                                      ("argument_formatter", "argument_formatters"),
                                      ("ui", "uis"), ("ui_factory", "ui_factories"),
                                      ("approval_channel", "approval_channels"),
                                      ("hook_factory", "hook_factories")],
}

KEYED_COLLECTIONS = {
    "zrb.llm.skill.registry:skill_registry": [("skill", "skills")],
    "zrb.llm.agent.subagent.registry:sub_agent_registry": [("agent", "agents")],
    "zrb.llm.hook.registry:hook_registry": [("hook", "hooks")],
}
```

- `test_every_ordered_collection_has_the_full_verb_set` — for each
  `(stem, plural)`, assert `append_<stem>`, `prepend_<stem>`, `set_<plural>`,
  `remove_<stem>` all exist and are callable, **and** `add_<stem>` does *not*
  exist (R5's no-alias clause).
- `test_every_keyed_collection_has_the_full_verb_set` — assert `add_<stem>`,
  `set_<plural>`, `remove_<stem>`, `get_<stem>`, `get_<plural>` exist; assert
  `append_<stem>` does *not*.
- `test_no_concept_is_reachable_by_two_names` (R7) — for every settable property
  `p` on each host, assert `set_<p>` and `set_<p singularized>` are not also
  methods. Keep the singularization dumb (strip a trailing `s`/`ies`→`y`) and
  hard-code the handful of irregulars rather than adding an inflection
  dependency.

Each assertion message names the host, the missing/extra verb, and the rule
number.

The dict literals above are the source of truth for what "uniform" means — a
new collection is added to the dict in the same diff that adds the collection.
Say so in a comment at the top of the file.

## Step 3.6 — Tests for the new verbs

The 45 new methods are behavior and need coverage. Do **not** create a
`test_*_extra.py` — update the existing files (`AGENTS.md` test conventions):

```bash
ls test/llm/task/ test/llm/task/chat/ test/llm/tool/test_registry.py
```

One parametrized test per host is enough, and is the lazy correct shape:

```python
@pytest.mark.parametrize("stem,plural", [("tool", "tools"), ("trigger", "triggers"), ...])
def test_ordered_verbs_round_trip(stem, plural):
    task = LLMChatTask(name="t")
    sentinel_a, sentinel_b = object(), object()
    getattr(task, f"append_{stem}")(sentinel_a)
    getattr(task, f"prepend_{stem}")(sentinel_b)
    assert getattr(task, plural)[:2] == [sentinel_b, sentinel_a]
    getattr(task, f"remove_{stem}")(sentinel_b)
    assert sentinel_b not in getattr(task, plural)
    getattr(task, f"set_{plural}")([sentinel_a])
    assert list(getattr(task, plural)) == [sentinel_a]
```

Some collections validate their members (tool policies, UIs) and will reject a
bare `object()`. For those, build a minimal real instance instead — check the
existing test file for the fixture it already uses; do not loosen production
validation to make the test pass.

If any collection's getter applies a `CFG` name-allowlist filter (tools do —
`CFG.LLM_TOOLS`), the round-trip assertion must run with that twin empty. Set it
explicitly in the test rather than relying on the ambient environment.

## Step 3.7 — Docs and changelog

- `docs/configuration/llm-collections.md` — the families table's "Mutation
  verbs" column becomes uniform; remove the three-bullet "the split is
  deliberate" explanation of why hooks differ (they no longer do). Keep the
  ordered-vs-keyed distinction, which is still real.
- Grep the docs tree for every deleted name and fix each:
  `grep -rn "get_search_directories\|set_history_manager\|set_approval_channel\|set_ui_factory\|hook_registry.register\|clear_manual" docs/`
  Skip `docs/changelog*` — changelogs record history and stay as written
  (project convention).
- Changelog entry: list every rename as a breaking change, old → new.

## Verification

```bash
cd /home/gofrendi/zrb
pytest test/architecture/test_mutation_surface.py -q
grep -rn "get_search_directories\|set_history_manager\|set_approval_channel" src/zrb docs/ | grep -v changelog
# expect no output
./zrb-test.sh
```

## Done when

`test_mutation_surface.py` passes with no exemptions, no deleted name survives
outside the changelogs, and `./zrb-test.sh` is green at ≥ 90%.

🔖 [Plan](README.md)
