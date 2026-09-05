# Maintainability Plan

Status: proposed, not started. Generated 2026-09-05 against `d6f8c5161` (v3.0.0a4).

This plan is written to be executed **one task at a time, in order**.
Every task states its exact files, the exact change,
the exact verification command, and a binary done-condition. Nothing says
"consider" or "you may want to".

**Out of scope for this plan (deliberately):** the package split
(`zrb` core / `zrb[llm]` / `zrb[web]`) and the transitive-only CVE pins in
`pyproject.toml`. Those are release-policy decisions, tracked separately.

---

## Ground rules

1. **One task per branch, one task per PR.** Do not batch tasks.
2. **`./zrb-test.sh` must pass before you open the PR.** It runs flake8 (F-class),
   pyright, the architecture ratchets in `test/architecture/`, and the full
   pytest suite at >=90% coverage. Nothing merges red.
3. **Do not lower a ratchet** in `test/architecture/` to make a task pass. If a
   ratchet blocks you, the task is wrong — stop and report it.
4. **No behaviour changes** in Tasks 1-5 unless the task says so explicitly.
   Task 2 is the only one that changes user-visible output on purpose.
5. **Follow `AGENTS.md`.** Especially: no cross-object private access
   (`self._a._b`), `# lazy: <reason>` on every in-function import, and the
   test-file naming conventions.
6. If a task's stated line numbers no longer match, re-run its **Find** command
   rather than guessing. Line numbers drift; the Find commands do not.

Every code snippet and every **Verify** block in this plan was executed against
`d6f8c5161` before the plan was written. Task 1's verify block currently fails
with 9 false positives (that is the bug); every other verify block currently
passes or describes the post-change state.

---

## Baseline metrics

Re-run these after each task to confirm the direction of travel.

```bash
# Total source and test size
find src/zrb -name '*.py' -exec cat {} + | wc -l        # 71962
find test    -name '*.py' -exec cat {} + | wc -l        # 91271

# UI methods reachable from outside the UI layer (the de-facto contract)
grep -rhoP '\bui\.\K[a-z_]+(?=\()' --include='*.py' \
  src/zrb/llm/tool_call src/zrb/llm/tool src/zrb/llm/agent \
  src/zrb/llm/task src/zrb/llm/approval src/zrb/runner | sort -u | wc -l   # 12

# UI methods tool_call/ uses
grep -rhoP '\bui\.\K[a-z_]+(?=\()' --include='*.py' src/zrb/llm/tool_call | sort -u   # 3

# BaseUI public surface
grep -cP '^    (async )?def [a-z]' src/zrb/llm/ui/base/ui.py                # 135

# Broad swallows
grep -rn 'except Exception' src/zrb --include='*.py' | wc -l                # 338
```

---

## Why this order

Measured over the last 180 days of git history:

| Area | LOC | fixes/kLOC | test-churn per src-churn | fan-in / fan-out |
|---|---:|---:|---:|---|
| `llm/tool_call` | 1,295 | **28.6** | — | 24 / 39 |
| `llm/agent` | 6,634 | 8.9 | 1.35 | **91 / 111** |
| `llm/tool` | 9,262 | 10.9 | **1.31** | 34 / 108 |
| `llm/ui` | 11,162 | 9.4 | 1.04 | 38 / 140 |

`llm/tool_call` is the worst per line and the cheapest to fix — it goes first.
`llm/agent` is the god module (the only area high on **both** fan-in and
fan-out) and is deliberately **last**, behind a test harness. `llm/ui` is bulky
but stable, below average on every pain metric — it is cleanup, not a wound.

---

## Corrections to earlier estimates

Three numbers quoted in the review discussion were wrong. The plan uses the
corrected ones.

| Claim | Corrected |
|---|---|
| "multi_ui.py is 883 lines of copy-paste" | 883 total, but **534 lines of real code** — 176 are docstrings and they are good docstrings. The realistic saving from Task 4 is **~90 lines**, not 800. |
| "62 silent swallows; naming the exception will find bugs" | 82 `except/pass` sites, but **63 already name a specific exception**. Only **21** are `Exception`/`BaseException`, and most of those are legitimate best-effort process kills. Task 5 targets **5**, not 62. |
| "define one event type crossing the agent/tool/UI boundary" | Unnecessary. The narrow contract already exists implicitly (3 methods). Task 3 writes it down; it invents nothing. |

---

# Task 1 — Fix `check_unrecommended_commands` false positives

**Size:** ~15 lines. **Risk:** none. **Depends on:** nothing.

## Why

`CFG.SHOW_UNRECOMMENDED_COMMAND_WARNING` defaults to `True`, and the check uses
naive substring matching. Today, every one of these prints a yellow WARNING:

```
'npm test'                    -> "Use '[' instead for consistency"
'cargo test'                  -> "Use '[' instead for consistency"
'go test ./...'               -> "Use '[' instead for consistency"
'make test'                   -> "Use '[' instead for consistency"
'pip install open-source-lib' -> "Not POSIX compliant; use '.' instead"
'aws s3 ls s3://bucket'       -> "Avoid using ls"
'grep --color foo bar'        -> "grep long commands do not work on Alpine"
```

This is the first thing a new user sees, on the oldest task type zrb ships.

## Files

- `src/zrb/util/cmd/command.py` — `check_unrecommended_commands`, lines 17-54
- `test/util/cmd/test_command.py` — add the regression cases

## Change

In `src/zrb/util/cmd/command.py`, the `banned_commands` dict is matched with
`if cmd in cmd_script`. Replace that substring match with a word-boundary regex
match, and drop the `" test"` entry entirely (it cannot be made correct — `test`
is a real subcommand of npm, cargo, go, make, pytest, and dotnet).

Before (lines 28-50, abridged):

```python
    banned_commands = {
        "<(": "Process substitution isn't POSIX compliant and causes trouble",
        "column": "...",
        "echo": "echo isn't consistent across OS; use printf instead",
        "eval": "...",
        "realpath": "...",
        "source": "Not POSIX compliant; use '.' instead",
        " test": "Use '[' instead for consistency",
        "which": "...",
    }
    ...
    for cmd, reason in banned_commands.items():
        if cmd in cmd_script:
            violations[cmd] = reason
```

After:

```python
    # Matched as whole words, not substrings: "source" must not fire on
    # "open-source", and "ls" must not fire on "tools". `<(` is punctuation
    # and has no word boundary, so it stays a substring check.
    banned_commands = {
        "column": "Command isn't included in Ubuntu packages and is not POSIX compliant",
        "echo": "echo isn't consistent across OS; use printf instead",
        "eval": "Avoid eval as it can accidentally execute arbitrary strings",
        "realpath": "Not available by default on OSX",
        "source": "Not POSIX compliant; use '.' instead",
        "which": "Command in not POSIX compliant, use command -v",
    }
    banned_substrings = {
        "<(": "Process substitution isn't POSIX compliant and causes trouble",
    }
    ...
    for cmd, reason in banned_commands.items():
        if re.search(rf"(?<![\w-]){re.escape(cmd)}(?![\w-])", cmd_script):
            violations[cmd] = reason
    for frag, reason in banned_substrings.items():
        if frag in cmd_script:
            violations[frag] = reason
```

Note `(?<![\w-])` / `(?![\w-])` rather than `\b`: the hyphen matters, so
`open-source` and `x-which-y` do not fire.

Also fix the two over-broad regexes in `banned_commands_regex`:

- `r"grep[^|]+--\w{2,}"` fires on `grep --color`. Narrow it to the long options
  that actually break on Alpine's busybox grep, or delete the entry.
- `r"\bls "` fires on `aws s3 ls s3://...`. Anchor it to a command position:
  `r"(?:^|[|;&]\s*)ls\s"`.

**Do not** remove the `echo` entry. It is noisy but it is correct, and it is
`CFG`-gated. Removing it is a product decision, not a bug fix.

## Verify

```bash
.venv/bin/python - <<'EOF'
from zrb.util.cmd.command import check_unrecommended_commands as c
must_be_clean = [
    "npm test", "cargo test", "go test ./...", "make test",
    "pip install open-source-lib", "aws s3 ls s3://bucket",
    "grep --color foo bar", "pytest -k test_thing", "dotnet test",
]
must_warn = ["echo hi", "source ./env.sh", "which python", "eval $x",
             "diff <(a) <(b)", "ls -la", "realpath ."]
bad = [s for s in must_be_clean if c(s)]
missed = [s for s in must_warn if not c(s)]
assert not bad, f"false positives: {bad}"
assert not missed, f"missed real warnings: {missed}"
print("OK")
EOF
```

## Done when

- The snippet above prints `OK`.
- Those 16 strings exist as parametrized cases in `test/util/cmd/test_command.py`.
- `./zrb-test.sh` passes.

---

# Task 2 — Delete the three unused UI factory helpers

**Size:** −330 lines. **Risk:** low (public API, pre-release). **Depends on:** nothing.

## Why

`src/zrb/llm/ui/ui_factory.py` exports three functions. Two of them are
one-line pass-throughs that add nothing:

```python
def create_bot_ui_factory(ui_class, config=None, **bot_kwargs) -> Callable:
    """<40 lines of docstring with a Telegram example whose body is `...`>"""
    return create_ui_factory(ui_class, config=config, **bot_kwargs)
```

`create_http_ui_factory` is the same, with `host`/`port` spelled out — and it
**shadows a genuinely different function of the same name** in
`src/zrb/runner/chat/http_ui.py`, which is the one that actually does the work.
Two different `create_http_ui_factory` in one codebase is a 3am bug.

`PollingUI` (`src/zrb/llm/ui/polling_ui.py`, 88 lines) is documented as "Level 3"
of the user extension ladder and has **zero** callers anywhere in `src/`.

The project is at `3.0.0a4`. Per the project's clean-break convention, no
back-compat shim.

## Files

- `src/zrb/llm/ui/ui_factory.py` — delete `create_bot_ui_factory` (lines 92-138)
  and `create_http_ui_factory` (lines 139-194). Keep `create_ui_factory`.
- `src/zrb/llm/ui/polling_ui.py` — delete the file.
- `src/zrb/llm/ui/__init__.py` — remove the three names from imports and `__all__`.
- `test/llm/ui/test_polling_ui.py` — delete.
- `test/llm/ui/test_ui_factory.py` — remove the two wrapper tests, keep the
  `create_ui_factory` tests.
- `test/llm/ui/test_ui_variants.py` — remove `PollingUI` cases.
- `docs/llm/llm-custom-ui.md` — rewrite as a **two**-level ladder
  (`SimpleUI`, `EventDrivenUI`). Remove the PollingUI section, its Mermaid node,
  its table rows, and the `create_bot_ui_factory` / `create_http_ui_factory`
  examples. Point HTTP users at `zrb.runner.chat.http_ui.create_http_ui_factory`.

## Find

```bash
grep -rn "PollingUI\|create_bot_ui_factory\|create_http_ui_factory" \
  src test docs README.md
```

Every hit outside `src/zrb/runner/chat/` and `test/runner/` must be gone when
you are finished.

## Verify

```bash
grep -rn "PollingUI\|create_bot_ui_factory" src test docs README.md   # expect no output
grep -rn "create_http_ui_factory" src | grep -v runner/chat           # expect no output
.venv/bin/python -c "import zrb.llm.ui as u; print(sorted(u.__all__))"
```

## Done when

- The two greps produce no output.
- `import zrb` and `import zrb.llm.ui` both succeed.
- `docs/llm/llm-custom-ui.md` describes exactly two levels.
- `./zrb-test.sh` passes.

---

# Task 3 — Write down the UI contract that already exists (`AgentOutput`)

**Size:** +1 file (~45 lines), 16 one-word type edits. **Risk:** low — types only,
no runtime change. **Depends on:** nothing. **This is the highest-value task in the plan.**

## Why

```
BaseUI public methods:                135
UI methods used outside llm/ui:        12
UI methods tool_call/ uses:             3
```

`llm/tool_call/` is 1,295 lines with the worst fix-density in the repo
(28.6 fixes/kLOC) and co-changes with `llm/ui` in 46% of commits that touch it.
It depends on **three** methods:

| Method | Call sites in `tool_call/` |
|---|---|
| `append_to_output(*values, end=..., kind=...)` | 11 |
| `ask_user(prompt, output_to_parent=...)` | 1 |
| `run_interactive_command(cmd, shell=...)` | 2 |

Typing those parameters as the full `AnyUI` is what lets the coupling grow. Type
them as a 3-method protocol and pyright — already clean, already run by
`zrb-test.sh` — makes reaching for method 4 a build failure.

**This pattern already exists in this codebase.** `src/zrb/llm/agent/activity.py`
defines `HasActivityTracking`, a 3-member `Protocol` used exactly this way by
`src/zrb/llm/tool/delegate.py`. Task 3 is "do what `activity.py` already does,
for the `tool_call` seam." Read that file first and copy its shape.

## Files

**Create** `src/zrb/llm/ui/agent_output.py`:

```python
"""The narrow UI contract that non-UI code is allowed to depend on.

`BaseUI` exposes 135 public methods. Everything outside `zrb.llm.ui` uses 12 of
them, and `zrb.llm.tool_call` uses the three below. Typing a parameter as
`AgentOutput` instead of `AnyUI` is what keeps that true: pyright fails the
build when a consumer reaches for a fourth method.

Adding a member here is a design decision, not a convenience. The architecture
ratchet in `test/architecture/test_agent_output_surface.py` caps the size.

Mirrors the pattern in `zrb.llm.agent.activity.HasActivityTracking`.
"""

from __future__ import annotations

from typing import Any, Protocol, TextIO, runtime_checkable


@runtime_checkable
class AgentOutput(Protocol):
    """What tool-call plumbing may ask of a UI. `AnyUI` satisfies this."""

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ) -> None:
        """Write output the way `print()` would, kept for later replay."""
        ...

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Ask the user a free-text question and return their answer."""
        ...

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run an interactive command, handing it the real terminal."""
        ...
```

The signatures above are copied verbatim from `src/zrb/llm/ui/any_ui.py`
(lines 43-48, 58-65, 82-84). If they have drifted, copy the current ones —
they must match exactly or pyright will reject `AnyUI` as a structural match.

**Retype these 16 sites** from `AnyUI` to `AgentOutput`. All 16 are in
`src/zrb/llm/tool_call/`:

| File | Lines |
|---|---|
| `tool_call/handler.py` | 28, 31, 66, 89, 119, 126, 174 |
| `tool_call/edit_util.py` | 18 |
| `tool_call/tool_policy/auto_approve.py` | 27 |
| `tool_call/tool_policy/bash_validation.py` | 118 |
| `tool_call/tool_policy/read_file_validation.py` | 12 |
| `tool_call/tool_policy/replace_in_file_validation.py` | 13 |
| `tool_call/response_handler/default.py` | 16 |
| `tool_call/response_handler/replace_in_file_response_handler.py` | 14 |
| `tool_call/argument_formatter/write_file_formatter.py` | 17 |
| `tool_call/argument_formatter/replace_in_file_formatter.py` | 16 |

Also update the `ToolPolicy`, `ArgumentFormatter` and `ResponseHandler` type
aliases in `src/zrb/llm/tool_call/middleware.py` to use `AgentOutput`.

**Do NOT retype** these — they hold, construct, or forward a whole UI and
legitimately need `AnyUI`:

- everything in `src/zrb/llm/task/` (`set_ui`, `append_ui`, `prepend_ui`, ...)
- `src/zrb/llm/agent/run/runner.py` (114, 529, 803, 864)
- `src/zrb/llm/agent/run/deferred_calls.py` (93, 209)
- `src/zrb/llm/tool/delegate.py:113`
- `src/zrb/llm/approval/terminal_approval_channel.py:26`

**Add the ratchet** `test/architecture/test_agent_output_surface.py`:

```python
"""AgentOutput is a deliberately narrow contract. Keep it narrow.

Raising MAX_MEMBERS means a new kind of thing crosses the tool_call -> ui
boundary. That is a design decision; make it on purpose, in review.
"""

from zrb.llm.ui.agent_output import AgentOutput

MAX_MEMBERS = 3


def _members() -> list[str]:
    # `dir()`, not `__protocol_attrs__`: the latter is Python 3.12+ and this
    # project supports 3.11 (see `requires-python` in pyproject.toml).
    return sorted(n for n in dir(AgentOutput) if not n.startswith("_"))


def test_agent_output_stays_narrow():
    members = _members()
    assert len(members) <= MAX_MEMBERS, (
        f"AgentOutput grew to {len(members)} members: {members}. "
        "Adding one couples more of the codebase to the UI layer."
    )


def test_any_ui_satisfies_agent_output():
    from zrb.llm.ui.any_ui import AnyUI

    for name in _members():
        assert hasattr(AnyUI, name), f"AnyUI is missing {name}"
```

## Find

```bash
grep -rn 'ui: "\?AnyUI' --include='*.py' src/zrb/llm/tool_call
grep -rn '\bui\.[a-z_]*(' --include='*.py' src/zrb/llm/tool_call
```

The second command must only ever show `append_to_output`, `ask_user`, and
`run_interactive_command`. If it shows a fourth, **stop** — that method belongs
in `AgentOutput` and the ratchet needs raising deliberately, or the call is a
layering violation to fix instead.

## Verify

```bash
pyright src/zrb                              # must be clean
grep -rn "AnyUI" src/zrb/llm/tool_call       # expect no output
.venv/bin/python -m pytest test/architecture test/llm/tool_call -q
```

## Done when

- `grep -rn "AnyUI" src/zrb/llm/tool_call` produces no output.
- `pyright src/zrb` is clean.
- Both tests in `test_agent_output_surface.py` pass.
- `./zrb-test.sh` passes.

## Follow-up (separate PR, only after this one merges)

Document the two UI propagation paths in `src/zrb/contextvars.py`. There are
37 explicit `ui:` parameters and 11 `get_current_ui()` calls, and the split is
**correct** — user-written tools read the ambient `current_ui` so they need no
`ui` parameter, while internal plumbing takes it explicitly. Three lines of
comment; change no code.

---

# Task 4 — Collapse the `MultiUI` fan-out duplication

**Size:** ~−90 lines of code. **Risk:** low. **Depends on:** Task 3 merged.

## Why

`src/zrb/llm/ui/multi_ui.py` is 883 lines, of which **534 are real code** (176
are docstrings, and those are worth keeping — do not delete them). It is the
**#2 fix magnet in the repo** (14 fix commits in 180 days).

About 17 of its 51 methods repeat one of two shapes:

```python
# Shape A - optional fan-out
for ui in self._uis:
    fn = getattr(ui, "mark_thinking_block_start", None)
    if callable(fn):
        try:
            fn()
        except Exception as e:
            CFG.LOGGER.debug(f"Child UI mark_thinking_block_start failed: {e}")

# Shape B - optional fan-out with an append_to_output fallback
#   (record_tool_call_block only)
```

## Change

Add one private helper, then reduce each Shape-A method to a single call.
**Keep every existing docstring exactly as it is** — they explain real
behavioural subtleties (which children get a fallback and why) that the code
does not.

```python
    def _fanout(self, method_name: str, /, *args, **kwargs) -> None:
        """Call `method_name` on every child that implements it.

        Children are best-effort: one child raising must not stop the others,
        because a MultiUI fans one agent run out to independent channels (TUI,
        SSE, Telegram) and a dead channel is not a dead run.
        """
        for ui in self._uis:
            fn = getattr(ui, method_name, None)
            if not callable(fn):
                continue
            try:
                fn(*args, **kwargs)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI {method_name} failed: {e}")
```

Then, for example:

```python
    def mark_thinking_block_start(self) -> None:
        """<keep the existing 8-line docstring verbatim>"""
        self._fanout("mark_thinking_block_start")

    def collapse_thinking_block(self, collapsed: str, full: str) -> None:
        """<keep the existing docstring verbatim>"""
        self._fanout("collapse_thinking_block", collapsed, full)
```

**Convert only Shape-A methods.** Leave alone:

- `append_to_output` and `stream_to_parent` — these call the method on *every*
  child unconditionally (no `getattr` guard). Different semantics.
- `record_tool_call_block` — Shape B, has an `append_to_output` fallback.
- `stream_ai_response` (complexity 19) — not a fan-out, leave it entirely.
- anything whose loop body is not exactly `getattr` + `callable` + `try`.

## Find

```bash
grep -n 'getattr(ui, "' src/zrb/llm/ui/multi_ui.py
```

Each hit is a candidate. Check each one's loop body matches Shape A before
converting it.

## Verify

```bash
.venv/bin/python -m pytest test/llm/ui -q
grep -c "Child UI .* failed" src/zrb/llm/ui/multi_ui.py   # was 19, expect <= 5
wc -l src/zrb/llm/ui/multi_ui.py                          # was 883, expect ~790
```

## Then merge the test files

`test/llm/ui/` has three files for this one module:
`test_ui_multi.py`, `test_multi_ui_state.py`, `test_multi_ui_fanout.py`.
`AGENTS.md` allows splitting >500-line test files **by feature group**, but
"fanout" and "state" and "multi" are not three feature groups — nobody can tell
where a new test goes. Merge into `test_multi_ui.py`; split again only if it
exceeds 500 lines, and then by a name that answers "where does my new test go".

Do the same for `test_buffered_output.py` / `test_buffered_ui_output.py` /
`test_buffered_ui_collapse.py`.

## Done when

- `grep -c 'Child UI .* failed' src/zrb/llm/ui/multi_ui.py` returns <= 5.
- `test/llm/ui/` has one `test_multi_ui.py` and one buffered-output test file.
- Coverage of `src/zrb/llm/ui/multi_ui.py` has not dropped.
- `./zrb-test.sh` passes.

---

# Task 5 — Narrow the five swallows that actually hide bugs

**Size:** ~5 sites. **Risk:** low. **Depends on:** nothing.

## Why

There are 82 `try/except/pass` sites, but **63 already name a specific
exception** and most of the remaining 21 are legitimate best-effort cleanup
(`process.kill()`, `pipe.close()`, `get_app().invalidate()`). Do **not** sweep
all 82 — that is busywork that changes nothing.

Five of them swallow real logic:

| Site | Swallowed |
|---|---|
| `src/zrb/task/base/lifecycle.py:192` | `task.get_ctx(session)` |
| `src/zrb/task/base/lifecycle.py:198` | `task.get_ctx(session)` |
| `src/zrb/task/base/monitoring.py:167` | `await action_coro` — an entire task action |
| `src/zrb/llm/tool/shell.py:310` | live shell output streaming |
| `src/zrb/llm/tool/shell.py:334` | final shell output capture |

The three in `task/` are in the **core task engine** — the part of zrb with the
best reputation and the least excuse for a silent failure.

## Change

For each site, in this order of preference:

1. Name the specific exception the code can actually raise. Read the callee to
   find out; do not guess.
2. If a broad catch is genuinely correct (it is at a fan-out or teardown
   boundary), keep `except Exception` but **replace `pass` with**
   `CFG.LOGGER.debug(f"<what was being attempted> failed: {e}")`. A swallow that
   logs is debuggable; a swallow that does not is not.
3. If neither applies, delete the try/except and let it raise.

Never leave a bare `pass` behind at these five sites.

## Verify

```bash
.venv/bin/python - <<'EOF'
import ast
for p, want in [("src/zrb/task/base/lifecycle.py", 2),
                ("src/zrb/task/base/monitoring.py", 1),
                ("src/zrb/llm/tool/shell.py", 2)]:
    t = ast.parse(open(p).read())
    n = sum(1 for x in ast.walk(t) if isinstance(x, ast.Try)
            for h in x.handlers
            if len(h.body) == 1 and isinstance(h.body[0], ast.Pass)
            and h.type is not None
            and ast.unparse(h.type) in ("Exception", "BaseException"))
    print(f"{p}: {n} broad silent swallows left (was {want})")
    assert n < want, p
EOF
```

## Done when

- The snippet above passes its asserts.
- Each changed site has a test in the mirrored `test/` path proving the error
  path is now observable (raised, or logged).
- `./zrb-test.sh` passes.

---

# Task 6 — Characterization tests for the agent run loop

**Size:** new test file, ~300 lines. **Risk:** none (tests only).
**Depends on:** Tasks 1-5 merged. **This is the real work.**

## Why

```
src/zrb/llm/agent/run/runner.py:  968 LOC, 17 fix commits in 180 days  <- #1 fix magnet
src/zrb/llm/agent/run/  cluster:  1,983 LOC, 37 fixes = 18.7/kLOC      <- 2x the UI rate
llm/agent fan-in/fan-out:         91 / 111                             <- the god module
```

`llm/agent` is the only area in the repo that is high on **both** fan-in and
fan-out. Everything else is a clean leaf (`util` 11/186, `config` 14/174) or a
clean consumer (`builtin` 171/1, `llm/ui` 140/38).

Co-change over 180 days, for commits touching `llm/agent`:

```
llm/skill       72%      llm/hook        54%
llm/config      71%      llm/tool_call   50%
llm/summarizer  67%      llm/approval    46%
```

Six subsystems cannot move without it.

**Do not restructure it yet.** 17 fixes in 180 days means its behaviour is still
being discovered. Refactoring the module you are still fixing weekly is how you
get fix #18. The repo-wide mock:assert ratio is 0.62 (5,732 mocks / 9,214
asserts) — this file specifically needs the opposite.

## Change

Create `test/llm/agent/run/test_runner_characterization.py`. Rules for this file:

- **No `MagicMock` on the code under test.** Mock only the model boundary
  (the pydantic-ai agent) and the UI, using a recording fake that appends to a
  list — not `AsyncMock`.
- Drive `run_agent` through its **public** entry point with a real message list
  in and assert on the real message list out. No private access
  (`test/architecture/test_private_test_access_ratchet.py` enforces this).
- One test per scenario, named for the scenario, not the method.

Cover at minimum:

1. A single turn with no tool calls: N messages in, N+1 out.
2. A turn with one approved tool call: the tool result lands in history in the
   right position, exactly once.
3. A turn with one **denied** tool call: the denial text reaches history and the
   tool did not run.
4. A stream error mid-turn: `retry_loop` retries, and history is not duplicated.
5. A cancelled run: partial output is preserved, history is not corrupted.
6. Summarization firing mid-run: the summary replaces the right span and the
   turn cursor still points at a valid index.
7. A deferred tool call resolving after the turn ends.

Each of these maps to at least one of the 17 fixes in the last 180 days. Before
writing a test, read the fix commits to find the real failure mode:

```bash
git log --since=180.days --grep='fix\|bug\|regress' -i --oneline -- \
  src/zrb/llm/agent/run/runner.py
```

Write the test that would have caught each one.

## Done when

- All seven scenarios are covered.
- The new file contains zero `MagicMock` and zero `_`-prefixed attribute access.
- `pytest test/llm/agent -q` passes.
- Coverage of `src/zrb/llm/agent/run/runner.py` is >= 90%.
- `./zrb-test.sh` passes.

## Only after this

With the harness green, the split becomes discussable. The co-change data points
at the fault line: `skill`, `config` and `summarizer` are things the runner
**configures** rather than **uses**. Extracting an `AgentSpec` that those three
populate and `runner.py` only reads would cut fan-in hard.

That is a design conversation, not a task. **Do not start it from this plan.**

---

# Explicitly not in this plan

Real findings, deliberately deferred. Do not do these while working the tasks above.

| Finding | Why deferred |
|---|---|
| Package split (`zrb` core / `zrb[llm]` / `zrb[web]`); 110 mandatory packages | Out of scope by instruction. Release-policy decision. |
| 11 transitive-only CVE pins in `pyproject.toml` | Same. Falls out of the split. |
| 9 `any_*.py` protocols with exactly one implementation (`AnyTask` = 25 abstract methods, 1 impl) | ~800 lines of mirror, but zero fix-density. Clean up when already in the file. |
| 91 ADRs vs ~24 user-facing docs | Real imbalance, no maintenance pain measured. |
| `BaseUI`'s 135 public methods | Task 3 fences the *consumers*, which is what matters. Shrinking `BaseUI` itself is a separate, larger job. |
| 8 LSP tools out of 26 default tools (~30% of the tool-schema budget) | Needs a token-cost measurement first, not a refactor. |
| `zrb-test.sh` runtime (~92s) | Known, previously deferred by the maintainer. |

---

# Summary

| Task | Change | Lines | Risk | Value |
|---|---|---:|---|---|
| 1 | Fix `check_unrecommended_commands` | ~15 | none | Highest user-visible |
| 2 | Delete 3 unused UI factory helpers | −330 | low | Removes a name collision |
| 3 | **`AgentOutput` protocol** | +45 / 16 edits | low | **Highest structural** |
| 4 | `MultiUI._fanout` | −90 | low | Modest |
| 5 | Narrow 5 real swallows | ~5 sites | low | Debuggability |
| 6 | **Runner characterization tests** | +300 | none | **Unblocks everything else** |

Tasks 1-5 are roughly two days and net about −380 lines. Task 6 is where the
actual maintainability work begins, and it begins with tests, not a refactor.
