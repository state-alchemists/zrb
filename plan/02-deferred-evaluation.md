🔖 [Plan](README.md)

# Phase 2 — Nothing reads config at import time; init failures are loud

Enforces **R3**, **R4**. Risk: low. Estimate: 1 day.

## The two bugs

### Bug A — two settings can never be changed from `zrb_init.py`

```bash
cd /home/gofrendi/zrb
grep -n "CFG\." src/zrb/builtin/todo.py | sed -n '1,2p'
grep -n "CFG\." src/zrb/builtin/searxng/start.py
```

- `src/zrb/builtin/todo.py:40` — `default=CFG.TODO_VISUAL_FILTER`
- `src/zrb/builtin/searxng/start.py:49` — `default=IntInput(name="port", default=CFG.SEARXNG_PORT)`

Both are evaluated while `zrb.builtin` is being imported, which happens **before**
`__main__.serve_cli()` loads any `zrb_init.py`. So `CFG.TODO_VISUAL_FILTER = "x"`
in `zrb_init.py` is a silent no-op. This is precisely the failure mode ADR-0090
Part 3 exists to prevent, and nothing tests for it.

### Bug B — a broken `zrb_init.py` prints one line and carries on

`src/zrb/__main__.py`, three times over:

```python
try:
    load_file(zrb_init_path)
except BaseException as e:
    print(stylize_error(f"{e}"), file=sys.stderr)
```

Three problems. `BaseException` catches `KeyboardInterrupt` and `SystemExit`.
`f"{e}"` drops the exception type and the traceback, so a `NameError` on line 40
of the user's file prints `name 'foo' is not defined` with no file and no line.
And execution continues, so the CLI runs with *half* the user's config applied —
the worst possible outcome, because the symptom appears somewhere else entirely.

## Step 2.1 — Fix the two eager reads

`BaseInput.default` already accepts "a literal, an f-string template rendered
against the context, or a callable taking it" (see the docstring in
`src/zrb/input/base_input.py`). Wrap both in a callable:

`src/zrb/builtin/todo.py:40`
```python
        default=lambda _: CFG.TODO_VISUAL_FILTER,
```

`src/zrb/builtin/searxng/start.py:49`
```python
        input=IntInput(name="port", default=lambda _: CFG.SEARXNG_PORT),
```

Confirm `IntInput` resolves a callable default the same way (it subclasses
`BaseInput` and only overrides `_parse_str_value`, so it does — but verify with
the check in §Verification, not by reading).

## Step 2.2 — Ratchet: no `CFG` read at import time (R3)

New file `test/architecture/test_deferred_config_reads.py`. Model it on
`test/architecture/test_lazy_import_categories.py` — same AST-walk shape, same
`REPO_ROOT`/`SRC` constants, same "collect all violations then assert on the
whole set" style so one run reports every offender.

The check: walk every module under `src/zrb`, find each `Attribute` node whose
`value` is a `Name` with `id == "CFG"`, and flag it when it is evaluated at
import time. It is evaluated at import time when **either**:

- its nearest enclosing scope is the module (no `FunctionDef`,
  `AsyncFunctionDef` or `Lambda` between it and `Module`), **or**
- it sits inside a `FunctionDef`/`AsyncFunctionDef`/`Lambda` node's
  `args.defaults` or `args.kw_defaults` list (a default argument is evaluated
  when the `def` executes, i.e. at import).

Implementation note for whoever writes it: the simplest correct way is one
recursive walk carrying a `deferred: bool` flag. Entering a function/lambda
**body** sets `deferred=True`; the function's `args.defaults` and
`args.kw_defaults` are visited with the *parent's* flag, not `True`. Flag any
`CFG.X` reached with `deferred=False`.

Exemptions — keep this list tiny and each entry justified in a comment:

```python
# Paths where an import-time CFG read is correct, not a bug.
EXEMPT_PREFIXES = (
    "config/",       # the config package defines CFG; its own reads are internal
    "__main__.py",   # runs after zrb_init.py has loaded, by construction
)
```

`src/zrb/util/init_path.py` reads `CFG.INIT_FILE_NAME` and `CFG.LOGGER` — both
inside `get_init_path_list()`, so they are already deferred and need no
exemption. Confirm before adding one.

Assertion message must list `path:line` plus the attribute name for every
violation, and end with the fix:
`"Wrap the read in a callable (lambda _: CFG.X) so zrb_init.py can still change it — R3, ADR-0090 Part 3."`

**Run it before fixing anything** to see the true offender count:
```bash
pytest test/architecture/test_deferred_config_reads.py -x 2>&1 | tail -40
```
The measured baseline is 2 (`builtin/todo.py`, `builtin/searxng/start.py`). If
the test reports more, the extras are real findings — fix them the same way, or
add a justified exemption only if the read genuinely cannot be deferred. Do not
add a numeric ratchet limit; the target is zero.

## Step 2.3 — Make init failures loud (R4)

`src/zrb/__main__.py`. Replace all three `try/except BaseException` blocks with
one shared helper, defined above `serve_cli`:

```python
def _load_or_die(label: str, load: "Callable[[], None]") -> None:
    """Load one init module/script, or report it precisely and exit non-zero.

    A partially applied config is worse than no config: the symptom shows up
    somewhere unrelated. So a failure here is fatal, and the message carries
    the file, the line and the exception type the user needs.
    """
    try:
        load()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        frame = traceback.extract_tb(error.__traceback__)[-1]
        print(
            stylize_error(
                f"Failed to load {label}\n"
                f"  {frame.filename}:{frame.lineno}\n"
                f"  {type(error).__name__}: {error}"
            ),
            file=sys.stderr,
        )
        sys.exit(1)
```

Add `import traceback` and `from typing import Callable` at the top.

Then the three call sites become:

```python
for init_module in CFG.INIT_MODULES:
    CFG.LOGGER.info(f"Loading {init_module}")
    _load_or_die(f"init module {init_module}", lambda m=init_module: load_module(m))
...
    _load_or_die(f"init script {abs_init_script}", lambda p=abs_init_script: load_file(p))
...
    _load_or_die(f"{zrb_init_path}", lambda p=zrb_init_path: load_file(p))
```

The `m=`/`p=` default-argument binding is required — a bare closure over the
loop variable captures the last value.

**This changes behavior: a broken `zrb_init.py` now aborts the CLI.** That is
the point (R4), and it is what makes "clear error message" true rather than
aspirational. Flag it prominently in the changelog entry.

**Decision needed if you disagree:** if you want a broken init to be
non-fatal, the alternative is to keep going but exit non-zero at the end and
print a summary of what failed to load. Say which you want; the plan assumes
fatal.

## Step 2.4 — Test the init-failure path

New file `test/test_main.py` — check whether one exists first
(`ls test/test_main.py`); `.coveragerc` omits `src/zrb/__main__.py` from
coverage, so this test exists for behavior, not for the coverage number.

Because `__main__.py` is coverage-omitted and calls `sys.exit`, test the helper
through its public entry point with a `tmp_path` init file:

```python
def test_a_broken_init_script_aborts_with_file_line_and_type(tmp_path, capsys, monkeypatch):
    broken = tmp_path / "zrb_init.py"
    broken.write_text("this_name_does_not_exist()\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    with pytest.raises(SystemExit) as excinfo:
        serve_cli()
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "zrb_init.py" in err
    assert "NameError" in err
```

If `serve_cli()` proves untestable in-process (it installs logging handlers and
runs the CLI), fall back to a subprocess assertion — same three checks on
`stderr` and the exit code:

```python
result = subprocess.run([sys.executable, "-m", "zrb"], cwd=tmp_path,
                        capture_output=True, text=True)
assert result.returncode == 1
assert "NameError" in result.stderr and "zrb_init.py" in result.stderr
```

Prefer the in-process version; use the subprocess only if the first genuinely
cannot be made to work.

## Step 2.5 — Note, not a task: one eager heavy import

Recorded here so it is not rediscovered as a mystery:

```bash
python -X importtime -c "import zrb" 2>&1 | sort -t'|' -k2 -rn | head -12
```

`zrb.builtin` → `builtin.group` → `runner.cli` → `config.web_auth_config` →
`runner.web_schema.user` costs ~60 ms of the 203 ms total, because the web
schema is pulled in eagerly by `web_auth_config`. Total startup is fine, so
**this is not in scope**. If startup ever becomes a complaint, that chain is
where the 60 ms is, and `test/architecture/test_lazy_import_categories.py`
category 2 ("transitively heavy via internal") is the rule that would cover it.

## Verification

```bash
cd /home/gofrendi/zrb
# Bug A: the settings now respond to zrb_init.py
mkdir -p /tmp/zrbcheck && cd /tmp/zrbcheck
cat > zrb_init.py <<'EOF'
from zrb import CFG
CFG.TODO_VISUAL_FILTER = "@work"
EOF
python -c "
import os; os.chdir('/tmp/zrbcheck')
from zrb.util.load import load_file
from zrb.builtin.todo import *      # tasks already defined
load_file('zrb_init.py')            # config set AFTER definition
from zrb.config.config import CFG
print('CFG now:', CFG.TODO_VISUAL_FILTER)
"
# Bug B
cd /tmp/zrbcheck && echo 'this_name_does_not_exist()' > zrb_init.py
python -m zrb; echo "exit=$?  (expect 1, with file/line/NameError above)"
cd /home/gofrendi/zrb
pytest test/architecture/test_deferred_config_reads.py -q   # expect 0 violations
./zrb-test.sh
```

## Done when

`test_deferred_config_reads.py` reports zero violations, a broken `zrb_init.py`
exits 1 with file/line/exception type, and `./zrb-test.sh` is green.

## As implemented (divergences from this plan)

Landed as `b781f427b` (Phase 2). The verb, the ratchet test, and the exit
behavior all landed as planned; three things came out differently:

- **The measured baseline was 3 eager reads, not 2.** Beyond `todo.py` and
  `searxng/start.py`, `src/zrb/runner/cli.py`'s `start-server` task baked
  `CFG.ROOT_GROUP_NAME` into its `description=f"..."` at import time — the
  same class of bug, found only once `test_deferred_config_reads.py` actually
  ran. `Task.description` has no deferred-render mechanism to lambda-wrap, so
  the fix there was different in kind from the other two: the description
  became static text (dropping the branded name from it), not a callable.
- **`load_file()` gained a new parameter this plan didn't anticipate.** §2.3
  assumed `__main__.py`'s three `try/except BaseException` blocks were the
  only place swallowing the error. In fact `load_file()` (`src/zrb/util/load.py`)
  already caught and logged exceptions internally, returning `None` — so
  `_load_or_die`'s `except Exception` had nothing to catch until `load_file`
  gained an opt-in `raise_on_error: bool = False` parameter, used only by the
  two fatal `zrb_init.py`-loading call sites. Existing lenient callers
  (plugin/skill/hook discovery) are unaffected by the default.
- **`docs/configuration/env-vars.md` gained a callout box documenting the new
  fatal-on-broken-init behavior** — not listed in §2.5's docs scope, added
  because the behavior change is user-visible enough to need it inline, not
  just in the changelog.

Everything else — `_load_or_die`'s shape (`Callable[[], Any]` in practice,
not `Callable[[], None]`), the AST-walk ratchet design, the in-process
`test/test_main.py` (no subprocess fallback needed), and the `todo.py`/
`searxng/start.py` lambda fixes — landed exactly as written.

🔖 [Plan](README.md)
