🔖 [Plan](README.md)

# Phase 5 — 73 constructor parameters → a guessable core

Risk: **high**. Estimate: 4 days. **Needs your decision before starting** (§0).

## The measurement

```bash
cd /home/gofrendi/zrb/src/zrb && python3 - <<'EOF'
import re
def params(path):
    src = open(path).read()
    body = re.search(r"    def __init__\(\n(.*?)\n    \) *(->|:)", src, re.S).group(1)
    return [l.strip().split(':')[0].split('=')[0].strip()
            for l in body.split('\n') if re.match(r"^        [a-z_]", l) and 'self' not in l]
a, b = params("llm/task/llm_task.py"), params("llm/task/chat/task.py")
print("LLMTask", len(a), "| LLMChatTask", len(b), "| shared", len(set(a) & set(b)))
print("LLMTask only:", sorted(set(a) - set(b)))
print("ChatTask only:", sorted(set(b) - set(a)))
common_a = [x for x in a if x in set(b)]; common_b = [x for x in b if x in set(a)]
print("shared params in the same order?", common_a == common_b)
EOF
```

Measured at 2.69.0:

- `LLMTask.__init__`: **52** parameters. `LLMChatTask.__init__`: **73**.
- **50 shared** — and they are in a **different order** in the two classes; the
  first divergence is at shared-parameter index 10, where `hook_manager` sits in
  `LLMTask` but `active_skills` sits in `LLMChatTask`.
- `LLMTask` only: `dynamic_yolo`, `summarize_commands`.
- `LLMChatTask` only: 23, of which 20 are UI concerns.
- `BaseUI.__init__`: **34** parameters, of which **16** are command-name lists.

Nobody guesses this. Nobody keeps two 50-parameter lists in sync by hand — and
they already have not.

## The finding that decides the design

`src/zrb/llm/ui/ui_config.py` already exists and its docstring says:

> This dataclass replaces 25+ individual parameters in BaseUI.__init__.

**It is real and in use** — `SimpleUI`, `EventDrivenUI`, `PollingUI` and
`runner/chat/http_ui.py` all take `config: UIConfig`. But `BaseUI` and
`LLMChatTask` were never migrated, so the project runs **two parallel UI
configuration paths**, and they disagree:

| Setting | `CFG` / `BaseUI` default | `UIConfig` default |
| --- | --- | --- |
| exit commands | `/q, :q, /bye, /quit, /exit` | `["/exit", "/quit"]` |
| info commands | `/info, /help` | `["/help", "/?"]` |
| load commands | `/load, /resume` | `["/load"]` |

Reproduce:
```bash
grep -n "DEFAULT_LLM_UI_COMMAND_EXIT\|DEFAULT_LLM_UI_COMMAND_INFO" src/zrb/config/mixins/llm_ui_commands.py
grep -n "exit_commands\|info_commands" src/zrb/llm/ui/ui_config.py
```

So `ZRB_LLM_UI_COMMAND_EXIT` changes the TUI and does nothing to the web or
Telegram UI, and `/bye` works in one and not the other. That is a demonstrable
predictability bug, and it is the reason to finish the migration rather than
start a new design: **the pattern was already chosen, applied to half the tree,
and left to rot.**

## §0 — The decision

| Option | What happens | Recommendation |
| --- | --- | --- |
| **A. Do nothing** | Add only a growth ratchet (§5.4) capping the parameter count. 73 params stay. | Cheapest. Take it if you would rather spend the 4 days on Phases 6–8. |
| **B. Finish the `UIConfig` migration** (§5.1–5.3) | The 20 UI params on `LLMChatTask` and the 16 command lists on `BaseUI` collapse into `UIConfig`; `UIConfig` reads its defaults from `CFG` so the two paths stop disagreeing. `LLMChatTask` → ~53 params, `BaseUI` → ~19. | **Recommended.** Fixes a real bug, extends a pattern the project already owns, no new concept. |
| **C. Also unify the 50 shared params into a shared base** (§5.5) | `LLMTask` and `LLMChatTask` can no longer drift. Larger, riskier diff. | Do it only after B lands and only if the drift keeps recurring. |

The rest of this file assumes **B**, with C written up as a follow-on.

## Step 5.1 — Make `UIConfig` read its defaults from `CFG`

`src/zrb/llm/ui/ui_config.py`. The hardcoded `field(default_factory=lambda: ["/exit", "/quit"])`
defaults are the second source of truth. Replace each with a read of the `CFG`
twin, deferred (R3 — a dataclass field default is evaluated when the instance is
built, which is fine, but a *module-level* read would not be):

```python
def _commands(knob: str) -> "Callable[[], list[str]]":
    """Default factory reading a `CFG.LLM_UI_COMMAND_*` twin at instantiation.

    Deferred on purpose: `zrb_init.py` may change the knob after this module
    is imported (R3, ADR-0090 Part 3).
    """
    return lambda: comma_list(getattr(CFG, knob))
```

```python
    exit_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_EXIT"))
    info_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_INFO"))
    ...
```

Check first how `CFG.LLM_UI_COMMAND_EXIT` is already parsed into a list — the
knob is a comma-separated string (`"/q, :q, /bye, /quit, /exit"`), and
`config/env_field.py` already exports `comma_list`. **Use the existing helper**;
do not write a second splitter. Verify:
```bash
grep -n "LLM_UI_COMMAND_EXIT" src/zrb/config/mixins/llm_ui_commands.py
grep -rn "LLM_UI_COMMAND_EXIT" src/zrb/llm/ | head
```
If `BaseUI` already resolves these knobs through a helper, call that helper from
`UIConfig` instead of re-deriving.

**This changes SimpleUI/web/Telegram behavior**: `/bye` and `/q` start working
there, `/?` stops (unless you add it to `DEFAULT_LLM_UI_COMMAND_INFO`). Decide
which default list wins per row — the `CFG` list is the shipped, documented one,
so prefer it — and record the choice in the changelog. Add `/?` to the `CFG`
default if you want to keep it.

Add fields to `UIConfig` for the command families it is currently missing
(`summarize`, `rewind`, `btw`, `voice`, `photo`, `plan`, `copy`) so it covers all
16. Once it does, delete `UIConfig.minimal()` if nothing but its own test uses it
(`grep -rn "UIConfig.minimal" src/zrb test`) — a second preset is a second thing
to keep in sync, and `UIConfig(exit_commands=["/exit"])` says it in one line.

## Step 5.2 — Route `BaseUI` through `UIConfig`

`src/zrb/llm/ui/base/ui.py` (1,409 lines, 34 `__init__` params). Replace the 16
command-list parameters with one:

```python
    def __init__(
        self,
        ctx,
        llm_task,
        history_manager,
        ui_config: UIConfig | None = None,
        ...
    ):
        self._ui_config = ui_config or UIConfig()
```

Then, inside `BaseUI`, every `self._exit_commands` read becomes
`self._ui_config.exit_commands`. Mechanical:

```bash
grep -n "_commands\b" src/zrb/llm/ui/base/ui.py src/zrb/llm/ui/base/*.py | wc -l
```

`BaseUICommands` (`ui/base/commands.py`, 608 lines) is a composed part that
reads these. Per ADR-0035 it must reach them through a **public** accessor on the
owner, never `self._owner._ui_config`. So add to `BaseUI`:

```python
@property
def ui_config(self) -> UIConfig:
    """The command names and UI behavior flags this UI was built with."""
    return self._ui_config
```

and have the parts read `self._owner.ui_config.exit_commands`.
`test/architecture/test_boundaries.py::test_no_part_reaches_another_objects_private_state`
enforces this — run it early and often in this step.

Keep `assistant_name`, `is_yolo`, `yolo_xcom_key` and
`conversation_session_name` on `UIConfig` (they are already fields) and drop
them from the `BaseUI` signature too. That takes `BaseUI.__init__` from 34 to
about 19.

## Step 5.3 — Route `LLMChatTask` through `UIConfig`

`src/zrb/llm/task/chat/task.py`. These 20 parameters become one
`ui_config: UIConfig | None = None`:

`ui_commands`, `ui_greeting`, `render_ui_greeting`, `ui_assistant_name`,
`render_ui_assistant_name`, `ui_jargon`, `render_ui_jargon`, `ui_ascii_art`,
`render_ui_ascii_art`, `markdown_theme`, `enable_rewind`, `snapshot_dir`,
`include_default_ui`, `interactive`, `show_ollama_models`,
`show_pydantic_ai_models`, `yolo_xcom_key`.

Two things to handle carefully:

1. **The `render_*` flags.** Each `ui_greeting`/`render_ui_greeting` pair is the
   `*Attr` doctrine from ADR-0005: the value may be an f-string template and the
   flag says whether to render it. Moving the pair into `UIConfig` means
   `UIConfig` gains `ui_greeting` **and** `render_ui_greeting`. That is correct —
   keep the pair, do not collapse it. `UIConfig` is a dataclass and can hold
   `StrAttr` values; the *rendering* stays where it is today (whatever calls
   `get_str_attr`). Grep for the current call to confirm:
   `grep -rn "render_ui_greeting" src/zrb/llm/`.
2. **`interactive` and `include_default_ui` may not be UI *config*.** Read their
   getters. If they select *which UI to build* rather than configure one, they
   belong on the task, not in `UIConfig`. Leave them on the task if so, and say
   why in the commit message.

Add the slot from Phase 4 so it is also settable after construction:

```python
@property
def ui_config(self) -> UIConfig: ...
@ui_config.setter
def ui_config(self, value: UIConfig) -> None: ...
```

## Step 5.4 — Ratchet: the surface cannot grow back

New file `test/architecture/test_constructor_surface.py`:

```python
# Max __init__ parameters per class. Lower these as the surface shrinks; a
# raise needs a one-line reason in the same diff, like the facade budgets.
PARAM_BUDGETS = {
    "zrb.llm.task.chat.task:LLMChatTask": 54,
    "zrb.llm.task.llm_task:LLMTask": 52,
    "zrb.llm.ui.base.ui:BaseUI": 20,
}
```

Two tests:

- `test_constructor_parameter_counts_stay_within_budget` — `inspect.signature`,
  count parameters excluding `self`.
- `test_the_two_task_classes_agree_on_their_shared_parameters` — compute the
  shared parameter names of `LLMTask` and `LLMChatTask` and assert their
  **relative order matches**. This is the drift detector; it fails today, so it
  must be written *after* the order is fixed. Fixing the order is a pure
  signature reshuffle (they are all keyword arguments — confirm with
  `grep -n "def __init__" -A 3 src/zrb/llm/task/chat/task.py` that there is a
  `*` marker or that every call site uses keywords; if any call site is
  positional, fix those call sites first).

If you take Option A, ship **only** this step, with the budgets set to today's
numbers (73 / 52 / 34). It costs an hour and stops the bleeding.

## Step 5.5 — Follow-on (Option C, not now)

If `LLMTask`/`LLMChatTask` keep drifting after B, the next move is a shared
`LLMTaskConfig` dataclass holding the 50 common parameters, with both classes
taking `config: LLMTaskConfig` plus their own extras. Do **not** start here:
it is a bigger diff than B, it does not fix a user-visible bug, and B may make
the drift small enough that C is not worth it. Revisit once
`test_the_two_task_classes_agree_on_their_shared_parameters` has failed twice
for real reasons.

## Step 5.6 — Docs

- `docs/advanced-topics/llm-custom-ui.md` (the "UIConfig: Cleaner Configuration"
  section at line ~759) currently presents `UIConfig` as the *SimpleUI* path and
  the 8-parameter mapping as separate. Rewrite: `UIConfig` is **the** UI
  configuration object, `CFG.LLM_UI_*` supplies its defaults, and the table at
  line ~50 comparing `SimpleUI` vs `BaseUI` no longer needs the "simplified
  `__init__`" distinction.
- `docs/configuration/llm-config.md` — grep for each of the 20 removed
  `LLMChatTask` parameters and rewrite those examples.
- Changelog: breaking. List the removed parameters and the `UIConfig` field that
  replaces each, plus the default-list changes from Step 5.1.

## Verification

```bash
cd /home/gofrendi/zrb
# The two UI paths now agree
python - <<'EOF'
from zrb.config.config import CFG
from zrb.llm.ui.ui_config import UIConfig
CFG.LLM_UI_COMMAND_EXIT = "/bye"
assert UIConfig().exit_commands == ["/bye"], UIConfig().exit_commands
print("ok: UIConfig follows CFG")
EOF
pytest test/architecture/test_constructor_surface.py -q
pytest test/llm/ui -q
./zrb-test.sh
```

## Done when

`UIConfig` derives every default from `CFG`, `BaseUI.__init__` is ≤ 20
parameters, `LLMChatTask.__init__` is ≤ 54, the shared-parameter order test
passes, and `./zrb-test.sh` is green.

## As implemented (divergences from this plan)

Option B was chosen and landed as `ec5fd4cb5` ("73 constructor parameters →
a guessable core (Phase 5, Option B)"). `BaseUI` beat its target; `LLMChatTask`
did not reach anywhere near its budget, because §5.3's own "handle carefully"
carve-outs turned out to cover most of the 20-parameter list, not a couple of
exceptions:

- **`LLMChatTask` collapsed 73 → 70 (4 parameters), not 73 → ~53 (20).** Only
  `yolo_xcom_key`, `ui_commands`, `show_ollama_models`, and
  `show_pydantic_ai_models` actually moved into `ui_config`. Excluded, and
  left on the task: the four `render_*` pairs (kept as task-level `*Attr`
  rendering, per §5.3 point 1 — but the *value* halves stayed on the task
  too, not just the render flags); `markdown_theme` (already its own Phase-4
  slot, so redundant to also route through `UIConfig`); `enable_rewind`/
  `snapshot_dir` (a rewind feature, not UI config); `interactive`/
  `include_default_ui` (task-level flow-control, exactly the §5.3 point 2
  case the plan flagged as a possible carve-out — it was one, for both).
  `BaseUI.__init__` did land at **15** (better than the ≤ 20 target).
- **The shipped `PARAM_BUDGETS` reflect this: `LLMChatTask: 70` and
  `BaseUI: 15`**, not the plan's `54`/`20`/`52`. `LLMChatTask` misses this
  plan's own "Done when" criterion (≤ 54) as a direct, expected consequence
  of the narrower collapse above — this is not drift to fix later, it is
  what actually turned out to be UI config versus task-level concern once
  each parameter was read individually.
- **§5.1's `comma_list` premise was wrong.** The plan assumes
  `CFG.LLM_UI_COMMAND_EXIT` is a raw comma-separated string needing the
  `comma_list` helper called explicitly. In fact `EnvField`'s own
  `cast=comma_list` (`src/zrb/config/mixins/llm_ui_commands.py`) already
  parses it into `list[str]` before `CFG` returns it — `UIConfig`'s
  `_commands()` factory ended up being `lambda: list(getattr(CFG, knob))` (a
  defensive copy), with no second `comma_list` call.

Everything else — `UIConfig.minimal()` deleted, all 16 command families
added, `assistant_name`/`yolo_xcom_key` routed through `CFG`/stabilized, the
two latent-bug fixes (SimpleUI missing `rewind`/`btw`/`voice`; the yolo xcom
key mismatch), `BaseUI` reaching `ui_config` only through a public accessor,
and the shared-parameter-order fix — landed exactly as written.

🔖 [Plan](README.md)
