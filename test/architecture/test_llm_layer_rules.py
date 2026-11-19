"""What a `zrb.llm` path scores, in both layouts at once.

Two layouts are legal during the 4.0 move: the old one, where a unit's layer
came from a table, and the new one, where the directory under `llm/` is the
layer. A tree half-way between them is what the move is made of, so these rules
are tested against paths rather than against the tree — the paths do not exist
yet, and they are the point.

The ratchet itself is `test_llm_layering_ratchet.py`, which applies these to
every import in the tree.
"""

from llm_layers import (
    LAYER_OF_UNIT,
    _LAYERS,
    _UNIT_DESTINATIONS,
    _is_upward,
    _layer,
    _path_in,
    _present_units,
    _unit,
)


def test_a_moved_path_is_scored_by_its_directory():
    """`contracts/config/…` is L0 because of where it sits, not what it is called."""
    assert _layer("contracts/config/ui_config.py") == 0
    assert _layer("capabilities/tool/shell.py") == 1
    assert _layer("engine/agent/run.py") == 2
    assert _layer("orchestration/task/base.py") == 3
    assert _layer("presentation/ui/default.py") == 4


def test_an_unmoved_unit_still_reads_the_table():
    """Half-moved is legal: a unit still in the old layout scores as it did before."""
    assert _layer("config/ui_config.py") == 0
    assert _layer("tool/shell.py") == 1
    assert _layer("agent/run.py") == 2
    assert _layer("task/base.py") == 3
    assert _layer("ui/default.py") == 4


def test_the_directory_wins_over_the_table():
    """The same name exists in both layouts mid-move, and the path decides."""
    assert _layer("capabilities/prompt/manager.py") == 1
    # The floors keep their old rule while they are still in `ui/`, and score L0
    # from the directory once they have moved under `contracts/`.
    assert _layer("ui/fallback/defaults/display.py") == 0
    assert _layer("contracts/ui_fallback/defaults/display.py") == 0


def test_an_upward_import_is_refused_in_both_layouts():
    """What makes one directory per pull request safe: a half-moved tree is judged."""
    assert _is_upward("contracts/config/x.py", "presentation/ui/y.py")
    assert _is_upward("capabilities/tool/x.py", "engine/agent/y.py")
    assert _is_upward("config/x.py", "agent/y.py")
    assert _is_upward("contracts/config/x.py", "agent/y.py")
    assert not _is_upward("presentation/ui/y.py", "contracts/config/x.py")
    assert not _is_upward("contracts/config/x.py", "contracts/shared/y.py")


def test_a_cycle_inside_one_ladder_directory_is_still_visible():
    """Two packages under one ladder directory are two units, not one."""
    assert _unit("capabilities/tool/shell.py") == "capabilities/tool"
    assert _unit("capabilities/prompt/manager.py") == "capabilities/prompt"
    assert _unit("orchestration/common_tools.py") == "orchestration/common_tools"
    assert _unit("contracts/__init__.py") == "contracts"
    assert _unit("tool/shell.py") == "tool"


def test_every_llm_unit_has_a_layer():
    missing = sorted(_present_units() - set(LAYER_OF_UNIT))
    assert not missing, (
        f"{missing} have no layer. Add each to _UNITS_BY_LAYER in llm_layers.py, "
        "or move it into the directory that scores it; a unit you cannot place "
        "is usually two units."
    )


def test_no_layer_names_a_unit_that_moved_away():
    stale = sorted(set(LAYER_OF_UNIT) - _present_units())
    assert not stale, (
        f"{stale} are scored but no longer exist under llm/. A name left behind "
        "by a move scores nothing and hides the unit that replaced it — delete "
        "the line, and give the package it moved into a layer if it has none."
    )


def test_every_unit_has_a_destination():
    """A unit with no destination is one the codemod would leave behind."""
    expected = set(LAYER_OF_UNIT) | {"ui/fallback", "ui/buffered"}
    missing = sorted(expected - set(_UNIT_DESTINATIONS))
    extra = sorted(set(_UNIT_DESTINATIONS) - expected)
    assert not missing and not extra, (
        f"undestined: {missing}; mapped but not a unit: {extra}"
    )


def test_each_destination_sits_in_a_layer_directory():
    unknown = sorted(
        destination
        for destination in _UNIT_DESTINATIONS.values()
        if destination.split("/")[0] not in _LAYERS
    )
    assert not unknown, f"these land outside the five directories: {unknown}"


def test_a_move_does_not_change_a_units_layer():
    """The move is a move: same code, same layer, a path that says which.

    This is the check the codemod is audited by — a destination in the wrong
    directory would quietly re-file a unit into another layer, and 250 rewritten
    module paths are exactly where a human stops noticing.
    """
    changed = {
        unit: (destination, _layer(_path_in(unit)), _layer(_path_in(destination)))
        for unit, destination in _UNIT_DESTINATIONS.items()
        if _layer(_path_in(unit)) != _layer(_path_in(destination))
    }
    assert not changed, f"unit: (destination, from, to) — {changed}"


def test_two_units_do_not_land_on_one_path():
    landing: dict[str, list[str]] = {}
    for unit, destination in _UNIT_DESTINATIONS.items():
        landing.setdefault(destination, []).append(unit)
    shared = {
        destination: units for destination, units in landing.items() if len(units) > 1
    }
    assert not shared, f"two units on one path: {shared}"
