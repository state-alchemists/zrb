"""The capability contracts must not drag the UI they are a part of.

`contracts/ui/` exists because a layer beneath `ui/` names these protocols:
`tool_call`, `approval`, `dictation` and `custom_command` type the user's output
and input side, and `tool/ask.py` builds a choice question. Importing one of
them has to cost that module and nothing else. If it pulled `zrb.llm.presentation.ui` in,
the capability would still be presentation's and the upward edge would only have
moved from import time to load time — the move would have bought the ratchet a
green line and nothing else.
"""

import os
import pathlib
import subprocess
import sys

# The venv's `zrb` may be an editable install of another checkout, so the probe
# states its own path — the same reason `test_every_llm_module_imports.py` does.
REPO_ROOT = pathlib.Path(__file__).parents[4]
SRC = REPO_ROOT / "src"

CAPABILITY_MODULES = (
    "zrb.llm.contracts.ui.any_agent_output",
    "zrb.llm.contracts.ui.any_ui_input",
    "zrb.llm.contracts.ui.any_ui_picker",
)


def _modules_loaded_by(module: str) -> list[str]:
    """Every module in a fresh interpreter after importing *module*."""
    script = f"import sys\nimport {module}\nprint('\\n'.join(sys.modules))\n"
    process = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        capture_output=True,
        text=True,
        check=True,
    )
    return process.stdout.split()


def test_a_capability_does_not_load_the_ui():
    for module in CAPABILITY_MODULES:
        dragged = sorted(
            name
            for name in _modules_loaded_by(module)
            if name.startswith("zrb.llm.presentation.ui")
        )
        assert not dragged, (
            f"importing {module} loads {dragged}. A capability that loads the UI "
            "is the upward edge this package exists to remove."
        )
