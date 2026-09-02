🔖 [Plan](README.md)

# Phase 4 — `llm_chat.prompt_manager = pm` works

Enforces **R8**. Risk: medium. Estimate: 2 days.

This is the phase closest to the stated goal. The goal document's own example
raises `AttributeError` today.

## The bug, reproduced

```bash
cd /home/gofrendi/zrb
python - <<'EOF'
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.prompt.manager import PromptManager
try:
    llm_chat.prompt_manager = PromptManager()
    print("FAIL: expected this to work already")
except AttributeError as e:
    print("reproduced:", e)
EOF
```

## The inventory

```bash
python - <<'EOF'
import inspect
from zrb.builtin.llm.chat import llm_chat
props = inspect.getmembers(type(llm_chat), lambda o: isinstance(o, property))
print("SETTABLE (%d):" % sum(1 for _, v in props if v.fset),
      sorted(n for n, v in props if v.fset))
print()
print("READ-ONLY (%d):" % sum(1 for _, v in props if not v.fset),
      sorted(n for n, v in props if not v.fset))
EOF
```

Measured: **8 settable, ~62 read-only.** And the 8 are arbitrary —
`readiness_failure_threshold` is settable, `retries` is not; `ui_factories` is
settable, `tools` is not. There is no rule a user could infer.

## Step 4.1 — Classify every property (do this before writing code)

Produce `plan/04-slot-inventory.md` (a working file, delete it when the phase
lands) with every property from the READ-ONLY list in exactly one bucket:

| Bucket | Meaning | Action |
| --- | --- | --- |
| **Slot** | Holds one replaceable component (`prompt_manager`, `hook_manager`, `llm_config`, `llm_limiter`, `history_manager`, `sandbox`, `permissions`) | **Make settable.** R8. |
| **Collection** | Holds a list already covered by Phase 3's verbs (`tools`, `toolsets`, `triggers`, `uis`, …) | **Leave read-only.** The verbs are the mutation surface; a settable list property would be a second way (R7). |
| **Resolved view** | Computed from other state (`model` from `llm_config` + `render_model`, `active_sections`, `has_prompt_manager`) | **Leave read-only.** Setting it would be a lie. |
| **Constructor datum** | Plain scalar fixed at definition time (`name`, `color`, `icon`, `description`, `cli_only`) | **Leave read-only.** Changing a task's name after registration breaks the CLI group tree. |
| **Task-graph** | `upstreams`, `fallbacks`, `successors`, `readiness_checks` | **Leave read-only**, covered by Phase 3 verbs. |

Rules for classifying, so two people get the same answer:

- If the type is an `Any*` ABC or a `*Manager`/`*Config`/`*Limiter` class → Slot.
- If the type is `list`/`Sequence`/`dict` → Collection.
- If the getter body calls another getter or a `get_*_attr` → Resolved view.
- If the getter body is `return self._x` and `_x` is a `str`/`bool`/`int` set only
  in `__init__` → Constructor datum.

Reviewer check on the finished table: every Slot row names the type its setter
will accept. If you cannot name the type, it is not a slot.

## Step 4.2 — Add the setters

For each Slot, in the owning part, then a delegator on the task (ADR-0035
composition rule — the part owns the state, the task re-exposes it):

```python
@property
def prompt_manager(self) -> PromptManager:
    """The prompt manager this task composes its system prompt with."""
    return self._prompt_manager

@prompt_manager.setter
def prompt_manager(self, value: PromptManager) -> None:
    """Replace the prompt manager wholesale — the ADR-0090 `set_*` layer."""
    self._prompt_manager = value
```

```python
# on the task
@property
def prompt_manager(self) -> PromptManager:
    return self._base_building.prompt_manager

@prompt_manager.setter
def prompt_manager(self, value: PromptManager) -> None:
    self._base_building.prompt_manager = value
```

**`has_prompt_manager` must go.** It exists because the manager is lazily
built; a read-only "is it there yet" flag is a leak of that internal state
(and violates R7 — two names for one question). Read the getter first:

```bash
grep -n "has_prompt_manager" -A 12 src/zrb/llm/task/chat/task.py src/zrb/llm/task/llm_task.py
grep -rn "has_prompt_manager" src/zrb test docs
```

If it exists to let a caller avoid *triggering* lazy construction, the fix is
for the getter to build on demand and for callers to stop asking. If it exists
only for a test, delete both.

**Type the setters, do not use `Any`.** `llm/task/llm_task.py` has 27 `: Any`
annotations, the most in the tree. A slot setter typed `Any` gives the user no
help from their editor and defeats the "prevent mistakes by type hinting" goal.
If the accepted type is genuinely open, that is a signal the slot needs an
`Any*` ABC — note it and hand it to Phase 8.

## Step 4.3 — Validate on assignment

A slot setter is a trust boundary: it accepts an object from user code that
production code will later call methods on. Assigning the wrong thing must fail
at the assignment, not three layers deep at run time — the same principle as
Phase 1 R2.

Where the slot's type is an ABC (`AnyHistoryManager`) or a concrete class,
one guard line:

```python
@history_manager.setter
def history_manager(self, value: AnyHistoryManager) -> None:
    if not isinstance(value, AnyHistoryManager):
        raise TypeError(
            f"{self._owner.name}.history_manager must be an AnyHistoryManager, "
            f"got {type(value).__name__}. Subclass "
            f"zrb.llm.history_manager.any_history_manager.AnyHistoryManager."
        )
    self._history_manager = value
```

Where the slot is a `Protocol` (not runtime-checkable), skip the isinstance
check — do not add `@runtime_checkable` just to enable it, and do not
hand-roll a duck-type check. Type hints carry it; note the gap in the docstring.

## Step 4.4 — Ratchet (R8)

Extend `test/architecture/test_mutation_surface.py` (from Phase 3 — do not
create a second file):

```python
# Every component a user may replace. Adding a slot means adding it here in
# the same diff. Type is the annotation its setter must accept.
SLOTS = {
    "zrb.builtin.llm.chat:llm_chat": [
        "prompt_manager", "hook_manager", "llm_config", "llm_limiter",
        "history_manager", "sandbox", "permissions",
    ],
    # ... one entry per host, from the Step 4.1 inventory
}


def test_every_declared_slot_is_settable_and_typed():
    ...
```

For each slot assert three things: the property exists, `fset is not None`, and
`typing.get_type_hints(prop.fset)` gives the value parameter a type that is not
`Any`. The third is what stops the surface degrading back to `Any`.

## Step 4.5 — The end-to-end test that mirrors the goal

New test in the existing `test/llm/task/chat/` file that owns task construction
(find it: `ls test/llm/task/chat/`). This is the acceptance test for the whole
plan, so make it read like the goal document:

```python
def test_a_user_can_swap_the_prompt_manager_after_the_task_is_defined():
    # Arrange — a task defined before any user config, as builtin/ does
    task = LLMChatTask(name="chat")
    replacement = PromptManager(registry=PromptRegistry())

    # Act — what a zrb_init.py does
    task.prompt_manager = replacement

    # Assert
    assert task.prompt_manager is replacement
```

Add the sibling for one registry delta and one `CFG` scalar, so the three
channels of ADR-0091 are each covered by a named test.

## Step 4.6 — Docs

- `docs/configuration/llm-collections.md` — the "Three configuration channels"
  section describes channel 3 ("replacing") for registries. Add the slot form:
  assigning a component to a host property, with `llm_chat.prompt_manager = ...`
  as the example. This is the channel-3 story for single components, and it is
  currently missing.
- `docs/configuration/llm-config.md` (931 lines) — grep it for any place that
  tells users to pass a component as a constructor argument *because* it cannot
  be set later. Those paragraphs are now wrong.
- Changelog: new capability, not a break (setters are additive; only
  `has_prompt_manager` is removed).

## Verification

```bash
cd /home/gofrendi/zrb
python - <<'EOF'
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.registry import PromptRegistry
pm = PromptManager(registry=PromptRegistry())
llm_chat.prompt_manager = pm
assert llm_chat.prompt_manager is pm
try:
    llm_chat.history_manager = "not a manager"
    print("FAIL: bad assignment accepted")
except TypeError as e:
    print("ok, rejected:", e)
print("ok")
EOF
pytest test/architecture/test_mutation_surface.py -q
./zrb-test.sh
```

## Done when

Every slot in the Step 4.1 inventory is settable with a non-`Any` type, a wrong
type raises `TypeError` naming the expected class, `has_prompt_manager` is gone,
and `./zrb-test.sh` is green.

## As implemented (divergences from this plan)

Landed as `ffc5f7869` (Phase 4) plus `5a354666e` (docstring follow-up),
scoped to `LLMChatTask` only (consistent with the plan's own examples, which
are all `llm_chat`-scoped, but never stated as a boundary). Five divergences:

- **`markdown_theme` shipped as an 8th slot.** §4.1's bucket table and §4.4's
  `SLOTS` sketch list 7 (`prompt_manager`, `hook_manager`, `llm_config`,
  `llm_limiter`, `history_manager`, `sandbox`, `permissions`). The real
  `SLOTS` dict and the real setters on `LLMChatTask` include `markdown_theme`
  too — found during the classification pass, not anticipated by the plan.
- **§4.1's working file `plan/04-slot-inventory.md` was never created.** The
  classification happened directly against the code rather than as a
  committed-then-deleted artifact.
- **§4.2's part-then-delegator template was not used.** Every slot's storage
  and property lives directly on `LLMChatTask` in `task.py` — no owning part,
  no delegator. This matches an existing repo convention
  `test/architecture/test_facade_size_budget.py` already documents ("this
  file's own docstring keeps that API on the task itself... since it is this
  task's own construction-time data — ADR-0035"), which this plan's snippet
  didn't account for.
- **`permissions` and `sandbox` deliberately skip §4.3's isinstance guard.**
  `PermissionPolicyInput`/`SandboxInput` are unions of convenient shapes, not
  one concrete class or ABC, so there is nothing to `isinstance`-check — a
  case the plan's "ABC or Protocol only" guidance didn't cover. Documented in
  each setter's own docstring instead.
- **`test/architecture/test_facade_size_budget.py`'s budget for
  `llm/task/chat/task.py` needed a bump (1100 → 1150)**, not mentioned
  anywhere in §4.4/§4.6 — the ratchet itself was added by Phase 3, one phase
  after this plan's own Phase 3 draft, so it wasn't yet a fixture the plan's
  author could reference.

`has_prompt_manager`'s removal matched the plan, and turned out to be the
simpler of the two contingencies §4.2 described: the getter's `ValueError`
branch was unconditionally dead code, not conditionally-dead-pending-a-test
as the plan hedged.

🔖 [Plan](README.md)
