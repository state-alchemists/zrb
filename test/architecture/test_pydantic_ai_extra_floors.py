"""zrb's provider extras must repeat pydantic-ai's own floors.

zrb depends on `pydantic-ai-slim[mcp]`, not on one extra per provider, so a
provider extra of pydantic-ai's never enters the resolution from here and its
floor has to be mirrored into `[project.optional-dependencies]` by hand. A missed
floor stays silent until runtime: `zrb[google]` allowed google-genai 2.25 while
pydantic-ai 2.61's Google model reads `usage_metadata.initial_prompt_token_count`,
which google-genai only grew in 2.30 — so every Gemini response carrying usage
metadata raised AttributeError, and the resolver had done nothing wrong.

Nothing here needs the provider SDKs installed: both sides are metadata.
"""

import tomllib
from importlib.metadata import requires
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

REPO_ROOT = Path(__file__).parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
PYDANTIC_AI = "pydantic-ai-slim"


def _floor(specifier: SpecifierSet) -> Version | None:
    """The version a specifier refuses to go below, or None when it names none."""
    for item in specifier:
        if item.operator == ">=":
            return Version(item.version)
    return None


def zrb_floors() -> dict[str, dict[str, Version]]:
    """{extra: {package: the lowest version zrb[extra] allows}}."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    extras = data.get("project", {}).get("optional-dependencies", {})
    floors: dict[str, dict[str, Version]] = {}
    for extra, entries in extras.items():
        for entry in entries:
            requirement = Requirement(entry)
            floor = _floor(requirement.specifier)
            if floor is not None:
                floors.setdefault(extra, {})[
                    canonicalize_name(requirement.name)
                ] = floor
    return floors


def pydantic_ai_floors(extras: set[str]) -> dict[str, dict[str, Version]]:
    """The same map, read from the installed pydantic-ai-slim's own extras.

    The marker is evaluated per extra name rather than parsed, so a requirement
    that also carries a platform condition still lands on the right extra.
    """
    floors: dict[str, dict[str, Version]] = {}
    for entry in requires(PYDANTIC_AI) or []:
        requirement = Requirement(entry)
        floor = _floor(requirement.specifier)
        if floor is None or requirement.marker is None:
            continue
        for extra in extras:
            if requirement.marker.evaluate({"extra": extra}):
                floors.setdefault(extra, {})[
                    canonicalize_name(requirement.name)
                ] = floor
    return floors


def test_the_extras_are_actually_parsed():
    """A parsing drift would make the invariant below hold vacuously."""
    zrb = zrb_floors()
    assert zrb, f"no lower bounds parsed from {PYPROJECT.name}'s optional dependencies"
    shared = sorted(set(zrb) & set(pydantic_ai_floors(set(zrb))))
    assert shared, (
        f"no extra of zrb's is also an extra of {PYDANTIC_AI} — the comparison "
        "below would pass without comparing anything"
    )


def test_every_mirrored_package_keeps_pydantic_ai_floor():
    zrb = zrb_floors()
    theirs = pydantic_ai_floors(set(zrb))
    violations = [
        f"zrb[{extra}] allows {package} {floor}, while {PYDANTIC_AI} requires "
        f">={theirs[extra][package]}"
        for extra, packages in zrb.items()
        for package, floor in packages.items()
        if package in theirs.get(extra, {}) and floor < theirs[extra][package]
    ]
    assert not violations, (
        "Raise the floor in pyproject.toml to pydantic-ai's own, or the resolution "
        "may legally install a version that pydantic-ai's provider code then fails "
        "against at runtime:\n  " + "\n  ".join(violations)
    )
