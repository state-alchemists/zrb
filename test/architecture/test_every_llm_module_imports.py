"""Every module under `zrb.llm` imports, so a stale path fails here, not for a user.

The 4.0 move rewrites 250 module paths, and the nets over it prove different
things. pyright reads a syntactic import. `test_public_api_contract.py` resolves
every name in `zrb.__all__` through the lazy-export table. Neither sees a path
typed as a *string* — a lazy export nobody re-exported, an
`importlib.import_module("zrb.llm.ui.session")`, a name in a factory table — and
after a move such a string stops resolving to anything the layering ratchet can
score: a silent pass, which is the one failure mode this tree has no net for.

So this is that net. It walks the tree, imports every module in one fresh
interpreter, and fails on any module that does not come back. Fresh, because
importing four hundred modules into the test session would leave `sys.modules`
holding state the next test did not ask for.

It reports; it does not judge. A module that fails is either a stale path — the
defect this exists for — or a module that was never importable, which is a
defect of the same size.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src"
LLM = SRC / "zrb" / "llm"

# Written as its own program so the interpreter that runs it shares no state with
# this one. `__pycache__` and other dunder paths are not modules.
_PROBE = """
import importlib, json, pathlib, sys

llm, report, base = (pathlib.Path(word) for word in sys.argv[1:4])
names = []
for path in sorted(llm.rglob("*.py")):
    parts = list(path.relative_to(base).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if any(part.startswith("__") for part in parts):
        continue
    names.append(".".join(parts))

failures = []
for name in names:
    try:
        importlib.import_module(name)
    except BaseException as error:
        failures.append([name, type(error).__name__, str(error)[:200]])

report.write_text(json.dumps({"modules": len(names), "failures": failures}))
"""


def _probe(
    tmp_path: Path,
    root: Path | None = None,
    base: Path | None = None,
    pythonpath: Path | None = None,
) -> dict:
    """The probe's report: how many modules it found, and which did not import.

    *root*, *base* and *pythonpath* are overridable so the probe can be pointed
    at a tree this test built, which is how it is proved to report anything at
    all. *base* is the directory a module's dotted name is read from.
    """
    report = tmp_path / "import-report.json"
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, str(root or LLM), str(report), str(base or SRC)],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(pythonpath or SRC)},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        "The import probe did not finish. Its stderr:\n" + result.stderr[-800:]
    )
    return json.loads(report.read_text(encoding="utf-8"))


def test_the_probe_reports_a_module_that_does_not_import(tmp_path):
    """A guard that only ever reports "clean" is a guard nobody has tested."""
    root = tmp_path / "somepkg"
    root.mkdir()
    (root / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "bad.py").write_text("import zrb.nothing_here\n", encoding="utf-8")

    report = _probe(tmp_path, root=root, base=tmp_path, pythonpath=tmp_path)

    assert report["modules"] == 2
    assert [name for name, *_ in report["failures"]] == ["somepkg.bad"]


def test_every_llm_module_imports(tmp_path):
    report = _probe(tmp_path)
    # A walk that found nothing would pass while proving nothing, so the count is
    # checked too: the tree holds hundreds of modules, and a floor that is wrong
    # by an order of magnitude means the walk broke, not that the tree shrank.
    assert report["modules"] > 100, f"the probe found {report['modules']} modules"
    assert not report["failures"], (
        "These modules do not import. A path that moved, or a string nothing "
        "rewrites, reads exactly like this:\n  "
        + "\n  ".join(
            f"{name}: {kind}: {message}"
            for name, kind, message in report["failures"]
        )
    )
