🔖 [Plan](README.md)

# Phase 1 — Config mistakes fail loudly, at the cause

Enforces **R1**, **R2**. Risk: low. Estimate: 1 day.

## The bug, reproduced

```bash
python - <<'EOF'
from zrb import CFG
CFG.LLM_MODELL = "oops"                              # typo
print("typo accepted silently:", CFG.LLM_MODELL)     # -> oops
CFG.LLM_MAX_REQUESTS_PER_MINUTE = "not-a-number"     # wrong type
print("wrong type accepted:", repr(CFG.LLM_MAX_REQUESTS_PER_MINUTE))
EOF
```

Both print. Neither raises.

**Why it matters.** `zrb_init.py` is the primary configuration channel. A typo
there is a silent no-op the user discovers as "why did my setting not apply".
A wrong type is worse: `EnvField.__set__` stores `str(value)` in `os.environ`
and the `int()` cast runs on the *next read*, so the traceback points at a
consumer hundreds of lines away from the assignment.

## Step 1.1 — Reject unknown `CFG` names (R1)

`src/zrb/config/config.py`. Add to the `Config` class body, after the existing
`is_env_set` method:

```python
def __setattr__(self, name: str, value: Any) -> None:
    """Reject an assignment to an UPPERCASE name this config does not define.

    `zrb_init.py` is configured by assignment, so a typo (`CFG.LLM_MODELL`)
    would otherwise be a silent no-op the user only notices as "my setting
    did not apply". Names that are not all-uppercase (internal `_state`) are
    left alone.
    """
    if name.isupper() and not hasattr(type(self), name):
        raise AttributeError(self._unknown_knob_message(name))
    super().__setattr__(name, value)

def _unknown_knob_message(self, name: str) -> str:
    known = sorted(
        n for n in dir(type(self)) if n.isupper() and not n.startswith("DEFAULT_")
    )
    suggestions = difflib.get_close_matches(name, known, n=3, cutoff=0.6)
    message = f"CFG has no setting named {name!r}."
    if suggestions:
        message += " Did you mean " + " / ".join(suggestions) + "?"
    return message + f" ({len(known)} settings; see `zrb config list`.)"
```

Add at the top of the file: `import difflib` and `from typing import Any`
(check whether `Any` is already imported before adding it).

**Two things to confirm before moving on:**

1. `hasattr(type(self), name)` must return `True` for both `EnvField`
   descriptors *and* the read-write properties on `FoundationMixin`
   (`ENV_PREFIX`, `ROOT_GROUP_NAME`, `ROOT_GROUP_DESCRIPTION`). Both are class
   attributes, so it does. Verify:
   `python -c "from zrb import CFG; CFG.ENV_PREFIX = CFG.ENV_PREFIX; CFG.ROOT_GROUP_NAME = CFG.ROOT_GROUP_NAME; print('ok')"`
2. `DEFAULT_*` constants are class attributes too, so
   `CFG.DEFAULT_LLM_MODEL = "x"` still works. That is intentional — leave it.

**Check the message against a real `zrb config list` command.** Run
`grep -rn "config" src/zrb/builtin/config.py | head -20`. If the actual
subcommand is named differently, use the real name in the message text. Do not
ship a message pointing at a command that does not exist.

## Step 1.2 — Validate on write (R2)

`src/zrb/config/env_field.py`. Replace `EnvField.__set__` (currently the last
method in the class) with:

```python
def __set__(self, obj: Any, value: Any) -> None:
    key = self.env_key(obj.ENV_PREFIX)
    if value is None:
        if self._nullable:
            os.environ.pop(key, None)
            return
        raise ValueError(
            f"CFG.{self._name} cannot be None — this setting has no null form. "
            f"Assign a {self._cast.__name__} value instead."
        )
    raw = self._serialize(value)
    try:
        self._cast(raw)
    except (ValueError, TypeError) as error:
        raise ValueError(
            f"CFG.{self._name} = {value!r} is not valid: it serializes to "
            f"{raw!r}, which {self._cast.__name__}() rejects ({error})."
        ) from error
    os.environ[key] = raw
```

**Why validate by round-tripping rather than by type-checking the input.**
`EnvField` already owns the pair `serialize` (write) / `cast` (read). A value is
valid exactly when `cast(serialize(value))` succeeds — that is the round trip
the config actually performs. Checking the input's Python type instead would
duplicate the knowledge and get list/bool fields wrong.

**`fallback` fields intentionally still raise here.** A field with
`fallback=...` degrades gracefully when the *environment* carries junk (not the
user's fault, and a crash at import is worse). An in-code assignment is the
user's fault and is exactly the case we want to catch. Do not consult
`self._fallback` in `__set__`.

## Step 1.3 — Fix whatever this breaks

```bash
cd /home/gofrendi/zrb && ./zrb-test.sh 2>&1 | tail -60
```

Expect failures. Triage each by this rule, and do **not** weaken Step 1.1/1.2
to make one pass:

| Failure shape | Fix |
| --- | --- |
| A test sets a knob to a value the cast rejects | The test was asserting the old silent behavior. Rewrite it to assert the new `ValueError`. |
| Production code assigns `None` to a non-nullable field | Real bug. Either mark the field `nullable=True` (if `None` is a meaningful value for it) or stop assigning `None`. |
| A test sets an invented knob name on `CFG` | Real bug — the test was not testing what it claimed. Use a real knob, or a purpose-built `Config` subclass. |
| A monkeypatch sets an attribute on `CFG` | Check `test/architecture/test_boundaries.py::MONKEYPATCH_EXCEPTIONS` — it already tracks these. Prefer `monkeypatch.setenv` on the real env key (`CFG.<field>.env_key(CFG.ENV_PREFIX)` gives it). |

## Step 1.4 — Tests

New file `test/config/test_config_assignment_safety.py` (add an empty
`test/config/__init__.py` if one is missing — see `AGENTS.md` on duplicate
basenames). Four tests, Arrange-Act-Assert, public API only:

```python
import pytest

from zrb.config.config import Config


def test_assigning_an_unknown_uppercase_knob_raises_and_suggests():
    cfg = Config()
    with pytest.raises(AttributeError) as excinfo:
        cfg.LLM_MODELL = "oops"
    message = str(excinfo.value)
    assert "LLM_MODELL" in message
    assert "LLM_MODEL" in message  # the suggestion


def test_assigning_a_known_knob_still_works():
    cfg = Config()
    cfg.LLM_MODEL = "anthropic:claude-opus-5"
    assert cfg.LLM_MODEL == "anthropic:claude-opus-5"


def test_assigning_an_uncastable_value_raises_at_the_assignment():
    cfg = Config()
    with pytest.raises(ValueError) as excinfo:
        cfg.LLM_MAX_REQUESTS_PER_MINUTE = "not-a-number"
    assert "LLM_MAX_REQUESTS_PER_MINUTE" in str(excinfo.value)


def test_a_read_write_property_is_still_assignable():
    cfg = Config()
    cfg.ROOT_GROUP_NAME = "myproject"
    assert cfg.ROOT_GROUP_NAME == "myproject"
```

`Config()` writes to the process `os.environ`, so use `monkeypatch.setenv`/
`monkeypatch.delenv` or a `Config` per test as the surrounding test files
already do — copy the isolation pattern from the existing `test/config/`
tests rather than inventing one.

## Step 1.5 — Docs

- `docs/configuration/env-vars.md` — add a short "Mistakes fail fast" section
  after the intro: an unknown `CFG` name raises and suggests; an uncastable
  value raises at the assignment.
- `docs/changelog-v2/` — add the entry to the current in-progress minor file,
  following the format in `docs/advanced-topics/maintainer-guide.md#changelog`.
  This is a **behavior change**: code that previously assigned a typo'd knob now
  raises. Say so.

## Verification

```bash
cd /home/gofrendi/zrb
python - <<'EOF'
from zrb import CFG
for expr, exc in [("CFG.LLM_MODELL = 'x'", AttributeError),
                  ("CFG.LLM_MAX_REQUESTS_PER_MINUTE = 'nope'", ValueError)]:
    try:
        exec(expr); print("FAIL (no raise):", expr)
    except exc as e:
        print("ok:", expr, "->", e)
CFG.LLM_MODEL = "anthropic:claude-opus-5"; print("ok: valid assignment")
EOF
./zrb-test.sh
```

## Done when

Both reproductions raise, the message names the closest real knob, and
`./zrb-test.sh` is green with coverage ≥ 90%.

🔖 [Plan](README.md)
