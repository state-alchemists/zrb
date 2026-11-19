"""What a `zrb.llm` path scores.

One layout: the directory under `llm/` is the layer. The table that scored a
unit which had not moved yet is gone, with the move that emptied it, so these
rules are tested against paths rather than against the tree — the interesting
paths are the ones a reader might still write, and a stale spelling is exactly
what has to keep scoring nothing.

The ratchet itself is `test_llm_layering_ratchet.py`, which applies these to
every import in the tree.
"""

from llm_layers import (
    LLM,
    _CONTRACT_PATHS,
    _LAYERS,
    _is_upward,
    _layer,
    _unit,
    _units_outside_the_ladder,
)


def test_a_moved_path_is_scored_by_its_directory():
    """`contracts/config/…` is L0 because of where it sits, not what it is called."""
    assert _layer("contracts/config/ui_config.py") == 0
    assert _layer("capabilities/tool/shell.py") == 1
    assert _layer("engine/agent/run.py") == 2
    assert _layer("orchestration/task/base.py") == 3
    assert _layer("presentation/ui/default.py") == 4


def test_a_path_outside_the_five_scores_nothing():
    """The old spelling of a moved module is not quietly L4; it has no layer.

    This is what makes a stale import visible: it is judged against nothing, so
    the ratchet's own reading of it cannot be mistaken for a legal edge.
    """
    assert _layer("camera/feature.py") is None
    assert _layer("ui/default.py") is None
    assert _layer("presentation/camera/feature.py") == 4
    assert _layer("presentation/ui/default.py") == 4


def test_a_floor_is_scored_by_its_prefix():
    """A floor scores below the package holding it, and its neighbours do not."""
    assert _layer("capabilities/prompt/manager.py") == 1
    assert _layer("presentation/ui/fallback/defaults/display.py") == 0
    assert _layer("presentation/ui/buffered/ui.py") == 0
    assert _layer("presentation/ui/defaults/display.py") == 4


def test_a_contract_is_scored_where_it_lives():
    """A file called `any_*.py` scores where it sits, not L0 by its name.

    The glob that used to grant it L0 was a table by another name: a reader
    could not tell from the path why a file at L4 was importable from L1. The
    contracts a lower layer must name have moved under `contracts/` instead, so
    these are the paths as the tree holds them.
    """
    assert _layer("presentation/ui/any_ui.py") == 4
    assert _layer("engine/agent/any_agent.py") == 2
    assert _layer("orchestration/subagent/any_sub_agent_manager.py") == 3
    # The one exemption left: the framework's own types, handed around by name.
    assert _layer("engine/agent/types.py") == 0


def test_a_contract_exemption_names_a_path_the_tree_has():
    """An exemption that outlives its path fails here rather than silently.

    `engine/agent/types.py` scores L0 wherever the run loop hands it around. An
    exemption naming a path the tree no longer has would exempt nothing, and the
    module it meant would be judged as the upward edge it only looks like.
    """
    for path in sorted(_CONTRACT_PATHS):
        assert (LLM / path).exists(), path


def test_a_floor_importing_its_own_package_contract_is_not_an_edge():
    """`presentation/ui/fallback` reaching `presentation/ui/any_ui.py` is one unit.

    The floor scores L0 and the contract it builds with scores L4, so the two
    layers say the pair is upward — and the ratchet never reports it, because
    `_file_edges` drops a pair whose ends share a unit. Both halves are pinned
    here so a reader who finds `_is_upward` returning True does not go "fix" a
    rule that is working.
    """
    assert (
        _unit("presentation/ui/fallback/echo_broadcast.py")
        == _unit("presentation/ui/any_ui.py")
        == "presentation/ui"
    )
    assert _layer("presentation/ui/fallback/echo_broadcast.py") == 0
    assert _layer("presentation/ui/any_ui.py") == 4


def test_an_upward_import_is_refused():
    assert _is_upward("contracts/config/x.py", "presentation/ui/y.py")
    assert _is_upward("capabilities/tool/x.py", "engine/agent/y.py")
    assert _is_upward("presentation/ui/fallback/x.py", "presentation/camera/y.py")
    assert _is_upward("contracts/config/x.py", "orchestration/subagent/y.py")
    assert not _is_upward("presentation/ui/y.py", "contracts/config/x.py")
    assert not _is_upward("contracts/config/x.py", "contracts/shared/y.py")


def test_a_cycle_inside_one_ladder_directory_is_still_visible():
    """Two packages under one ladder directory are two units, not one."""
    assert _unit("capabilities/tool/shell.py") == "capabilities/tool"
    assert _unit("capabilities/prompt/manager.py") == "capabilities/prompt"
    assert _unit("orchestration/common_tools.py") == "orchestration/common_tools"
    assert _unit("contracts/__init__.py") == "contracts"
    assert _unit("tool/shell.py") == "tool"


def test_llm_holds_only_the_five_directories():
    """The end of the move, pinned: a sixth directory would score no layer.

    The table and the destination map are gone, so nothing would place a unit
    that appeared at the top of `llm/` — every import it makes would be judged
    against no layer at all. This is the guard that says `llm/` is the five and
    nothing else.
    """
    directories = {
        path.name
        for path in LLM.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert directories == set(_LAYERS)
    assert _units_outside_the_ladder() == set()
