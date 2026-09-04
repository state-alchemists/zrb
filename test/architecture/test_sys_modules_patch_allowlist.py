"""Ratchet on `patch.dict("sys.modules", ...)` — it deletes real imports.

`unittest.mock.patch.dict` restores by `in_dict.clear()` followed by
`in_dict.update(saved_snapshot)`. Applied to `sys.modules` that is not a
restore but a **truncation**: every module imported for the first time
*inside* the with-block is absent from the snapshot, so exiting the block
deletes it.

For a pure-Python module that costs a re-import. For a C extension built with
single-phase init it is fatal and permanent: the shared object stays loaded in
the process while its `sys.modules` entry is gone, so the next `import` of it
raises `ImportError: cannot load module more than once per process` (a hard
error since CPython 3.12) for the rest of that worker's life.

That is not hypothetical. `VoiceEngine.record` lazily does `import numpy`
inside `test/llm/voice/test_engine.py`'s
`patch.dict("sys.modules", {"sounddevice": ...})`. Whichever `TestRecord` test
ran first on a worker imported numpy, the block exit evicted it, and the next
one died re-importing numpy's `_multiarray_umath` C extension. (Spelled
without its dotted path on purpose — `test_private_test_access_ratchet.py`
greps for `something` dot `_private` and cannot tell prose from code, so a
literal dotted example here inflates that ratchet's count.) It failed
roughly one full run in
five, because `pytest-xdist --dist load` hands out tests individually — so
whether the one `TestRecord` test that imports numpy *before* entering the
patch (and therefore immunizes the worker) lands on the same worker as the
other two is a coin flip. `test/conftest.py`'s
`_warm_modules_shadowed_by_sys_modules_patches` fixes it by importing numpy
once per worker, before any test runs, so the snapshot contains it.

**What to do when this test fails.** You added a new
`patch.dict("sys.modules", ...)`. Ask one question: *can the code inside the
block trigger a real, first-time import?* That means the module the block
shadows (if the code falls through to importing it for real) or — the case
that actually bit us — any other module a lazy `import` underneath it pulls
in. If yes, add that module to `_warm_modules_shadowed_by_sys_modules_patches`
so it is resident before the snapshot is taken. Then add the shadowed name
below with a one-line note.

This is an allowlist of *names*, not a count: what needs review is a new kind
of shadow, not another instance of one already reasoned about. Mirrors
`test_lazy_import_categories.py`'s reasoning for not ratcheting counts.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
TEST_ROOT = REPO_ROOT / "test"

# Module names the suite shadows in `sys.modules`, each reviewed for whether
# the guarded code can trigger a real first-time import underneath it.
#
# The value is why it is safe today. "mock-only" means the code under test
# never falls through to a real import — it reads attributes off the mock and
# returns, so nothing new enters `sys.modules` inside the block.
REVIEWED_SYS_MODULES_SHADOWS = {
    # Warmed in conftest: agent-hook code paths do `from pydantic_ai.toolsets
    # import ...` for real while the parent package is mocked.
    "pydantic_ai": "warmed (pydantic_ai.toolsets)",
    "pydantic_ai.models.openai": "mock-only; resolved via the warmed parent",
    # Warmed in conftest: `VoiceEngine.record` really does `import numpy`
    # inside the block, and numpy is a single-phase-init C extension.
    "sounddevice": "warmed (numpy, imported for real alongside it)",
    # mock-only: the transcriber factories read names off the fake module.
    "vosk": "mock-only",
    "openai": "mock-only",
    "google": "mock-only",
    "google.genai": "mock-only",
    "google.genai.types": "mock-only",
    "pyperclip": "mock-only",
    "tiktoken": "mock-only",
    # mock-only: the RAG tool reads `PersistentClient` / `OpenAI` off the fakes.
    "chromadb": "mock-only",
    "chromadb.config": "mock-only",
}

# The dict literal passed to `patch.dict("sys.modules", {...})`. Non-greedy to
# the first `}` — every call site in this suite passes a flat dict of
# module-name -> mock, so there is no nested brace to run past.
_PATCH_DICT_BODY = re.compile(
    r"""patch\.dict\(\s*["']sys\.modules["']\s*,\s*\{(.*?)\}""",
    re.DOTALL,
)
# Every quoted key inside that literal — a call may shadow several at once
# (`test/llm/tool/test_rag.py` shadows chromadb, chromadb.config and openai).
_DICT_KEY = re.compile(r"""["']([\w.]+)["']\s*:""")


def _shadowed_module_names() -> dict[str, set[str]]:
    """Map each shadowed module name to the test files that shadow it."""
    found: dict[str, set[str]] = {}
    for path in TEST_ROOT.rglob("*.py"):
        # This file's own regexes and allowlist would match themselves.
        if path == Path(__file__):
            continue
        text = path.read_text(encoding="utf-8")
        for body in _PATCH_DICT_BODY.findall(text):
            for name in _DICT_KEY.findall(body):
                found.setdefault(name, set()).add(str(path.relative_to(REPO_ROOT)))
    return found


def test_sys_modules_shadows_are_reviewed():
    """Every `patch.dict("sys.modules", ...)` target is on the allowlist."""
    found = _shadowed_module_names()
    unreviewed = {
        name: sorted(files)
        for name, files in found.items()
        if name not in REVIEWED_SYS_MODULES_SHADOWS
    }
    assert not unreviewed, (
        'New `patch.dict("sys.modules", ...)` target(s) — patch.dict deletes '
        "every module first imported inside the block, which is unrecoverable "
        "for a C extension. Check whether the guarded code can trigger a real "
        "first-time import; if so warm that module in test/conftest.py's "
        "`_warm_modules_shadowed_by_sys_modules_patches`. Then list the name in "
        f"REVIEWED_SYS_MODULES_SHADOWS. Unreviewed: {unreviewed}"
    )


def test_allowlist_has_no_stale_entries():
    """A name nobody shadows any more must leave the allowlist."""
    found = _shadowed_module_names()
    stale = sorted(set(REVIEWED_SYS_MODULES_SHADOWS) - set(found))
    assert not stale, (
        "REVIEWED_SYS_MODULES_SHADOWS lists module(s) no test shadows any "
        f"more — delete them: {stale}"
    )


def test_warmed_modules_are_importable():
    """The conftest warm-list must actually resolve.

    A typo'd or renamed module name would make the fixture a silent no-op —
    its `except ImportError: pass` is there for genuinely optional extras, and
    would swallow the mistake. These two are installed as real dependencies,
    so failing to import them means the name is wrong, not that an extra is
    missing.
    """
    import importlib

    for module_name in ("pydantic_ai.toolsets", "numpy"):
        assert importlib.import_module(module_name) is not None
