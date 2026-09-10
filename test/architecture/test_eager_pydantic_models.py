"""Keeps pydantic's model machinery out of every `import zrb`.

Declaring a `BaseModel` subclass at module level is what costs: it eagerly
loads `pydantic.main` and the schema-construction machinery behind it — worth
~19ms on `import zrb`, paid by whichever module in the closure declares one
first, and separate from whatever pydantic submodules are already loaded.

The 23 `llm/tool/*.py` modules that do `from pydantic import Field` are not
free — measured at ~31ms for `pydantic.fields` plus `pydantic.types` — but
they do not pull `pydantic.main` or the schema-construction machinery, which
is what this file is about. Deferring `Field` is a separate, larger question:
it is evaluated at `def` time inside `Annotated[...]` tool signatures, so it
cannot simply move into a function body.

So the fix is never "convert the model to a dataclass" — the models here are
pydantic on purpose, and two of them (`web_schema/token.py`'s
`RefreshTokenRequest`, `web_schema/session.py`'s `NewSessionResponse`) are
FastAPI request/response schemas that must stay that way. The fix is to keep
the declaring *module* out of the eager closure:

- `runner/web_schema/user.py` — deferred in `config/web_auth_config.py`
  (every annotation there was already a string) and behind `zrb/__init__.py`'s
  PEP-562 `__getattr__`, which is what kept `zrb.User` in the closure.
- `session_state_log/session_state_log.py` — deferred in `session/session.py`
  and `session_state_logger/file_session_state_logger.py`.

Adding a module-level model to something already in the closure silently
undoes all of it, which is what this catches.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src"

# The base every pydantic model in this repo is declared against.
_MODEL_BASE = "BaseModel"

# Modules allowed to declare a model *inside the closure*. Empty on purpose:
# every model this repo has is reachable lazily. An entry here means a module
# pays the machinery cost for every `import zrb`, and needs a reason.
ALLOWED_MODEL_MODULES: set[str] = set()


def _clean_env() -> dict[str, str]:
    """A near-empty environment, so the developer's own exported knobs cannot
    steer what a fresh interpreter imports.

    Windows needs a handful of its own variables inside that minimum. Without
    `SYSTEMROOT` the interpreter cannot load the Winsock provider, and zrb's
    own import chain reaches `import asyncio` — which imports `_overlapped` on
    win32 and dies with `WinError 10106` before a single zrb module is
    recorded.
    """
    env = {"PYTHONPATH": str(SRC), "HOME": str(Path.home())}
    if sys.platform != "win32":
        env["PATH"] = "/usr/bin:/bin"
        return env
    for name in (
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "COMSPEC",
        "PATHEXT",
        "PATH",
        "TEMP",
        # `Path.home()` runs during zrb's import chain, and ntpath's
        # expanduser reads these -- never HOME.
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
    ):
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    return env


def _closure_of(target: str) -> set[str]:
    """The `zrb.*` modules a clean interpreter loads when importing *target*."""
    code = (
        "import json, sys; import %s; "
        "print(json.dumps([m for m in sys.modules if m.startswith('zrb')]))" % target
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=_clean_env(),
    )
    assert result.returncode == 0, f"import {target} failed: {result.stderr[-2000:]}"
    return set(json.loads(result.stdout))


def _declares_a_model(path: Path) -> bool:
    """Whether *path* subclasses pydantic's model base at module level."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    return any(
        isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == _MODEL_BASE for base in node.bases
        )
        for node in tree.body
    )


def _declaring_modules_in(closure: set[str]) -> set[str]:
    found = set()
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC)
        name = ".".join(rel.parts)[: -len(".py")].removesuffix(".__init__")
        if name in closure and _declares_a_model(path):
            found.add(name)
    return found


def test_importing_zrb_declares_no_pydantic_model():
    declaring = _declaring_modules_in(_closure_of("zrb")) - ALLOWED_MODEL_MODULES
    assert not declaring, (
        "Module(s) declare a pydantic model inside `import zrb`'s closure: "
        f"{sorted(declaring)}. That loads pydantic's schema machinery for every "
        "run. Keep the module out of the closure with a deferred import (see "
        "`config/web_auth_config.py::_user_cls`) rather than changing the model."
    )


def test_importing_the_task_engine_declares_no_pydantic_model():
    """The DAG engine is usable without the agent stack; it must not pay for it."""
    declaring = _declaring_modules_in(_closure_of("zrb.task.task"))
    declaring -= ALLOWED_MODEL_MODULES
    assert (
        not declaring
    ), f"`import zrb.task.task` declares pydantic model(s): {sorted(declaring)}."
