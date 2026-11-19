"""Where a `zrb.llm` module sits in the ladder, as the guards see it.

Two files use this: `test_llm_layer_rules.py` holds the rules about a path — every
unit has a layer, a moved path is read from its directory — and
`test_llm_layering_ratchet.py` applies them to every import in the tree. They must
agree on what a unit is and what a layer is, and two copies of that would
eventually disagree, so the reading lives here once.

Nothing here asserts. These are the accessors; the rules and their reasons are
in the guard that applies them.
"""

import fnmatch
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src"
LLM = SRC / "zrb" / "llm"

# The table, for a unit that has not moved into the five-directory layout yet.
# It is deleted when the last one has (the P7 step of the 4.0 move).
_UNITS_BY_LAYER = {
    0: "config memory shared util",
    1: (
        "approval history_manager hook lsp permission prompt sandbox skill "
        "snapshot tool tool_call"
    ),
    2: "agent summarizer",
    3: "common_tools custom_command resumed_session subagent task",
    4: "camera dictation emotion screenshot speech ui voice",
}
LAYER_OF_UNIT = {
    unit: layer for layer, units in _UNITS_BY_LAYER.items() for unit in units.split()
}

# The 4.0 layout: the directory under `llm/` *is* the layer, so a reader — or an
# agent — stops needing a table to know where an import may point. A unit that
# has not moved yet still scores from `_UNITS_BY_LAYER`, which is what lets the
# move happen one directory per pull request instead of in one commit.
_LAYERS = {
    "contracts": 0,
    "capabilities": 1,
    "engine": 2,
    "orchestration": 3,
    "presentation": 4,
}

# Files that exist to be depended on, wherever they live.
_CONTRACT_NAME = "any_*.py"
_CONTRACT_PATHS = {"agent/types.py"}

# Path prefixes that sit below the layer of the package holding them. A floor is
# a part of a package that the layers beneath it must be able to build with:
# `ui/fallback/` is the plain terminal UI that a headless run needs, and it
# cannot drag `ui/` with it, so it scores L0 while its neighbours score L4.
# `ui/buffered/` is the same shape for delegation — `tool/delegate/runner.py`
# builds one buffer per sub-agent and hands it to `subagent/live_session.py` —
# and its own runtime imports, `output_chunk` and `tracked_spans` included, now
# sit at L0 beside it. The unit still ends up in the allowlists above if it
# reaches back up.
_FLOOR_PREFIXES = {"ui/fallback/": 0, "ui/buffered/": 0}


def _is_contract(path: str) -> bool:
    return path in _CONTRACT_PATHS or fnmatch.fnmatch(
        path.rsplit("/", 1)[-1], _CONTRACT_NAME
    )


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
    """The layer a path scores: its floor, its name, its directory, or the table."""
    for prefix, layer in _FLOOR_PREFIXES.items():
        if path.startswith(prefix):
            return layer
    if _is_contract(path):
        return 0
    directory = _LAYERS.get(path.split("/")[0])
    if directory is not None:
        return directory
    return LAYER_OF_UNIT.get(_unit(path))


def _is_upward(source: str, target: str) -> bool:
    """Whether *source* sits in a layer beneath *target*'s."""
    source_layer, target_layer = _layer(source), _layer(target)
    return (
        source_layer is not None
        and target_layer is not None
        and source_layer < target_layer
    )


def _present_units() -> set[str]:
    """The units `_UNITS_BY_LAYER` must describe: real modules, not artefacts.

    A directory counts only when it holds at least one `.py` file. Without that
    test, a `__pycache__` left behind by a moved module reads as a unit that
    exists but has no layer, and sends the reader hunting for code already gone.

    A ladder directory is skipped: it is scored by its path, and the table's job
    is the units that have not moved yet.
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


# Where everything lands when the tree is sorted into five directories: the plan
# as data, read off the tree the 4.0 shape describes. A unit mapped to a path
# ending in `.py` stays a loose module; everything else becomes a package.
#
# This is written down here, rather than in the prose of the plan, because the
# codemod that performs the move reads a map and the guards audit it: a
# destination that disagrees with the table, or two units landing on one path, is
# a typo a human would not catch in 250 rewritten module paths.
_UNIT_DESTINATIONS = {
    # contracts — what every layer builds with
    "config": "contracts/config",
    "memory": "contracts/memory",
    "shared": "contracts/shared",
    "util": "contracts/util",
    "ui/fallback": "contracts/ui_fallback",
    "ui/buffered": "contracts/ui_buffered",
    # capabilities
    "approval": "capabilities/approval",
    "history_manager": "capabilities/history_manager",
    "hook": "capabilities/hook",
    "lsp": "capabilities/lsp",
    "permission": "capabilities/permission",
    "prompt": "capabilities/prompt",
    "sandbox": "capabilities/sandbox",
    "skill": "capabilities/skill",
    "snapshot": "capabilities/snapshot",
    "tool": "capabilities/tool",
    "tool_call": "capabilities/tool_call",
    # engine
    "agent": "engine/agent",
    "summarizer": "engine/summarizer",
    # orchestration
    "common_tools": "orchestration/common_tools.py",
    "custom_command": "orchestration/custom_command",
    "resumed_session": "orchestration/resumed_session.py",
    "subagent": "orchestration/subagent",
    "task": "orchestration/task",
    # presentation
    "camera": "presentation/camera",
    "dictation": "presentation/dictation",
    "emotion": "presentation/emotion",
    "screenshot": "presentation/screenshot",
    "speech": "presentation/speech",
    "ui": "presentation/ui",
    "voice": "presentation/voice",
}


def _path_in(prefix: str) -> str:
    """A representative path for a unit or destination, for asking its layer."""
    return prefix if prefix.endswith(".py") else f"{prefix}/x.py"
