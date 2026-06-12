"""Rewrite the in-repo README to a PyPI-friendly variant.

PyPI renders the README as the package landing page, so any relative `docs/X`
links in the source README would resolve against `pypi.org`, not GitHub, and
break. This script reads `README.md` (the single source of truth, with
relative links that work locally and on GitHub), rewrites every relative
`docs/X` link to an absolute, **tag-pinned** GitHub URL, and writes the
result to `README.pypi.md` (the file Poetry packages).

Tag-pinning means a user landing on `pypi.org/project/zrb/<version>/` sees
docs as they existed at that release — even if `main` later reorganises.
Zrb's release tags are bare `major.minor.patch` (no `v` prefix), so the
generated URLs use `/blob/<version>/...` rather than `/blob/v<version>/...`.

`README.pypi.md` is a build artifact; it should be in `.gitignore`.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "README.md"
DST = ROOT / "README.pypi.md"
PYPROJECT = ROOT / "pyproject.toml"


def main() -> int:
    data = tomllib.loads(PYPROJECT.read_text())
    project = data["project"]
    version = project["version"]
    repo_url = project["urls"]["repository"].rstrip("/")
    base = f"{repo_url}/blob/{version}"

    text = SRC.read_text()

    # Match markdown links whose target is a relative path under docs/.
    # Captures the full link text in group 1 and the relative path in group 2.
    rewritten, n = re.subn(
        r"\]\((docs/[^)\s]+)\)",
        rf"]({base}/\1)",
        text,
    )

    DST.write_text(rewritten)
    print(f"wrote {DST.relative_to(ROOT)} ({n} doc links rewritten to {base}/...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
