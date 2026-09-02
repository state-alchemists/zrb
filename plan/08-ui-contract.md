🔖 [Plan](README.md)

# Phase 8 — Name and place the UI contract

Enforces **R9**. Risk: **low** (revised down — see §0). Estimate: 1.5 days.

## §0 — A correction to the plan's own framing

The README lists G12 as "the UI is the least swappable thing users most want to
swap." That reading was wrong, and the correction matters because it changes the
work:

```bash
cd /home/gofrendi/zrb
sed -n '10,50p' src/zrb/llm/ui/__init__.py       # the five-level ladder
wc -l docs/advanced-topics/llm-custom-ui.md
```

The UI **is** swappable, and well so. `src/zrb/llm/ui/__init__.py` documents a
five-level ladder — `SimpleUI` needs 2 methods, `EventDrivenUI` 2, `PollingUI` 1,
`BaseUI` 5 — plus `append_ui_factory` for running several channels at once, and
`docs/advanced-topics/llm-custom-ui.md` is a 1,000-line guide. `BaseUI` being
1,409 lines is the ceiling of the ladder, not its entry point.

**So this phase does not restructure the UI.** It fixes three real, small
defects. If you were expecting the big UI refactor implied by the README, this
is the honest scope instead; the four days it would have cost are better spent
on Phase 5.

## Defect 1 — There is no `AnyUI`, breaking a 13-for-13 convention

```bash
grep -rn "^class Any" src/zrb --include="*.py"
```

Every abstract extension point in the project is `Any<Thing>` in
`any_<thing>.py`: `AnyTask`, `AnyInput`, `AnyEnv`, `AnyGroup`, `AnySession`,
`AnyCallback`, `AnyContext`, `AnySharedContext`, `AnyCmdVal`,
`AnyContentTransformer`, `AnySessionStateLogger`, `AnyHistoryManager`,
`AnyCustomCommand`. Thirteen for thirteen.

The UI is the fourteenth extension point and it is called `UIProtocol`.

**Rename `UIProtocol` → `AnyUI`.** It stays a `typing.Protocol` — R9 governs the
name and location, not the mechanism, and a Protocol is the right mechanism here
(a UI is structural; nothing should have to inherit to be one). Note in the class
docstring that it is a Protocol rather than an ABC, and why, so the next reader
does not "fix" it into an ABC for consistency's sake.

## Defect 2 — The UI contract lives in the wrong package

```bash
grep -rn "tool_call.ui_protocol" src/zrb --include="*.py"
```

`UIProtocol` lives in `src/zrb/llm/tool_call/ui_protocol.py`, but it is the
canonical UI type for the whole subsystem: `llm/task/llm_task.py` annotates
`ui`, `_uis`, `_ui_factories`, `set_ui`, `append_ui`, `get_uis` and the `uis`
property with it, and `llm/agent_state.py` imports it too. A type that names the
`ui` slot on every task does not belong under `tool_call/`. It is there for
historical reasons (tool confirmation was the first consumer).

**Move it to `src/zrb/llm/ui/any_ui.py`** — the package that owns the concept,
the filename R9 requires.

Watch for a cycle: `llm/ui/__init__.py` imports `BaseUI`, which pulls in
`prompt_toolkit`-adjacent modules, so `from zrb.llm.ui.any_ui import AnyUI` must
**not** go through the package `__init__`. Import the module path directly at
every call site, and check that `test/architecture/test_lazy_import_categories.py`
and `test_circular_import_allowlist.py` both stay green — they are the reason
this move is a 30-minute job rather than a 30-minute job plus a day of debugging.

Update the call sites (measured: `llm/task/llm_task.py` ×7,
`llm/agent_state.py` ×1, plus `llm/tool_call/` internals):

```bash
grep -rln "ui_protocol" src/zrb test docs
```

Re-export `AnyUI` from `zrb/__init__.py` and add it to `__all__` — every other
`Any*` extension point is exported, and a user implementing a UI should be able
to `from zrb import AnyUI`.

## Defect 3 — The ladder diagram is out of date

`src/zrb/llm/ui/__init__.py` line ~15 says:

> UIProtocol … - 4 methods: ask_user, append_to_output, stream_to_parent, run_interactive_command

It has **six**: `ask_user`, `ask_user_choice`, `append_to_output`,
`stream_to_parent`, `run_interactive_command`, `run_async`.

```bash
grep -cE "^    (async )?def " src/zrb/llm/tool_call/ui_protocol.py   # 6
```

A "4 methods" promise that costs the reader two `NotImplementedError`s at run
time is exactly the surprise the goal is about. Fix the count and the list, in
the module docstring **and** in `docs/advanced-topics/llm-custom-ui.md` (the
comparison table at line ~50 carries the same numbers — verify each row against
the source rather than only the one you noticed).

## Step 8.1 — Ratchet (R9)

New test in `test/architecture/test_boundaries.py` (it already owns naming and
layering rules — do not add a seventh file):

```python
def test_every_extension_point_is_named_any_thing_in_any_thing_py():
    """R9. Thirteen extension points follow this; a fourteenth must too."""
    offenders = []
    for path in SRC.rglob("*.py"):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.ClassDef):
                continue
            if not _is_extension_point(node):     # ABC base, or Protocol base
                continue
            expected_file = f"any_{_snake(node.name.removeprefix('Any'))}.py"
            if not node.name.startswith("Any") or path.name != expected_file:
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno} {node.name}")
    assert not offenders, ...
```

Run it **before** making any change to see the true offender list:

```bash
pytest test/architecture/test_boundaries.py -k extension_point -x 2>&1 | tail -30
```

Expect more than one hit. Triage honestly rather than exempting:

- A `Protocol` used as a *structural annotation for a stdlib-ish shape*
  (something like a file-like or a callback signature) is not an extension point.
  Tighten `_is_extension_point` to exclude it, and say what the rule is in a
  comment.
- A `Protocol`/ABC that names a **slot on a public object** is an extension
  point. Rename it.
- Exemptions go in a module-level dict with a one-line reason each, the same
  shape `MONKEYPATCH_EXCEPTIONS` already uses in that file. If the exemption list
  grows past three, the rule is wrong — come back and narrow it rather than
  padding the list.

## Step 8.2 — Docs

- `docs/advanced-topics/llm-custom-ui.md` — global rename `UIProtocol` → `AnyUI`,
  fix the import path, fix the method counts in the level table.
- `src/zrb/llm/ui/__init__.py` module docstring — same.
- `AGENTS.md` "Inside `llm/`" table: the `app/`, `ui/` row says
  "the UI protocol plus its implementations (`ui/`)". After the move that is
  finally true — before it, the protocol was elsewhere. No edit needed, but
  confirm.
- Changelog: breaking (import path + class name). One-line migration:
  `from zrb.llm.tool_call.ui_protocol import UIProtocol` →
  `from zrb import AnyUI`.

## Step 8.3 — Note for Phase 4, not a task here

`llm/task/llm_task.py:442` defines a **settable** `uis` property, while the same
concept on `LLMChatTask` came back read-only in the Phase 4 inventory. That is a
Phase 3/4 asymmetry, not a UI defect. Record it in the Phase 4 Step 4.1
inventory so it is resolved there — the two classes must agree.

## Verification

```bash
cd /home/gofrendi/zrb
python -c "from zrb import AnyUI; print(AnyUI)"
grep -rn "UIProtocol\|tool_call.ui_protocol" src/zrb test docs | grep -v changelog
# expect no output
pytest test/architecture/ -q
./zrb-test.sh
```

## Done when

`AnyUI` lives in `src/zrb/llm/ui/any_ui.py`, is exported from `zrb`, the name
`UIProtocol` survives only in changelogs, the ladder diagram states six methods,
and `./zrb-test.sh` is green.

🔖 [Plan](README.md)
