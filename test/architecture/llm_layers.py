"""Where a `zrb.llm` module sits in the ladder, as the guards see it.

Two files use this: `test_llm_layer_rules.py` holds the rules about a path —
every unit is scored by the directory it sits in — and
`test_llm_layering_ratchet.py` applies them to every import in the tree. They must
agree on what a unit is and what a layer is, and two copies of that would
eventually disagree, so the reading lives here once.

Nothing here asserts. These are the accessors; the rules and their reasons are
in the guard that applies them.
"""

import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src"
LLM = SRC / "zrb" / "llm"

# The 4.0 layout: the directory under `llm/` *is* the layer, so a reader — or an
# agent — stops needing a table to know where an import may point. It took one
# directory per pull request, and the table that scored a unit which had not
# moved yet was emptied by the last of them and deleted here.
_LAYERS = {
    "contracts": 0,
    "capabilities": 1,
    "engine": 2,
    "orchestration": 3,
    "presentation": 4,
}

# The one file that is depended on without being scored where it sits: `agent/types.py`
# re-exports the pydantic-ai types the run loop hands around by the names the
# framework gave them, so it is a facade rather than a module of its own.
# Everything else is scored by its directory — and that includes `any_*.py`,
# which used to score L0 by its filename. The glob granted a rank by name, which
# is a table by another name: a reader could not tell from the path why a file
# at L4 was importable from L1. The contracts a lower layer must name now live
# where the path says so (`contracts/ui/`, `contracts/shared/`), which is what
# the move of #970, #972 and #973 bought.
_CONTRACT_PATHS = {"engine/agent/types.py"}

# Path prefixes that sit below the layer of the package holding them. A floor is
# a part of a package that the layers beneath it must be able to build with:
# `presentation/ui/fallback/` is the plain terminal UI that a headless run needs,
# and it cannot drag `presentation/ui/` with it, so it scores L0 while its
# neighbours score L4. `presentation/ui/buffered/` is the same shape for
# delegation — `capabilities/tool/delegate/runner.py` builds one buffer per
# sub-agent and hands it to `orchestration/subagent/live_session.py` — and its
# own runtime imports, `output_chunk` and `tracked_spans` included, now sit at L0
# beside it. The unit still ends up in the allowlists above if it reaches back
# up. The `AnyUI*` protocols these two floors build with stay in
# `presentation/ui/`, beside the implementers that answer them: sent down to
# `contracts/` they would import `presentation/` back at it, which is the edge
# the floors exist to avoid.
_FLOOR_PREFIXES = {"presentation/ui/fallback/": 0, "presentation/ui/buffered/": 0}


def _is_contract(path: str) -> bool:
    return path in _CONTRACT_PATHS


def _unit(path: str) -> str:
    """The package a path belongs to, at the granularity a cycle is judged at.

    That is the directory under `llm/` holding the file — except under a ladder
    directory, where it is the package one level in. Without the second rule all
    of `capabilities/` would be one unit, and a cycle between
    `capabilities/tool/` and `capabilities/prompt/` would stop being visible.
    """
    parts = path.split("/")
    if parts[0] in _LAYERS and len(parts) > 1:
        inner = parts[1].removesuffix(".py")
        return parts[0] if inner == "__init__" else f"{parts[0]}/{inner}"
    return parts[0].removesuffix(".py")


def _layer(path: str) -> int | None:
    """The layer a path scores: its floor, its exemption, or its directory.

    A path outside the five directories scores nothing, which is what makes a
    stale spelling of a moved module visible rather than silently L4.
    """
    for prefix, layer in _FLOOR_PREFIXES.items():
        if path.startswith(prefix):
            return layer
    if _is_contract(path):
        return 0
    return _LAYERS.get(path.split("/")[0])


def _is_upward(source: str, target: str) -> bool:
    """Whether *source* sits in a layer beneath *target*'s."""
    source_layer, target_layer = _layer(source), _layer(target)
    return (
        source_layer is not None
        and target_layer is not None
        and source_layer < target_layer
    )


def _units_outside_the_ladder() -> set[str]:
    """Directories under `llm/` that are not one of the five, and loose modules.

    There are none, and this is how the guards say so: a directory that appears
    at the top of `llm/` is a unit that would score no layer at all, so its
    imports would be judged against nothing. A directory counts only when it
    holds at least one `.py` file — without that test a `__pycache__` left behind
    by a moved module reads as a unit and sends the reader hunting for code
    already gone.
    """
    units: set[str] = set()
    for path in LLM.iterdir():
        name = path.name
        if name.startswith("_") or name == "__pycache__" or name in _LAYERS:
            continue
        if path.is_dir():
            if any(path.rglob("*.py")):
                units.add(name)
        elif path.suffix == ".py":
            units.add(name.removesuffix(".py"))
    return units
