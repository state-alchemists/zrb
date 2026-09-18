"""Cover the mutation ratchet's own operators.

The script under test is what decides whether the suite asserts or only
executes, so a silent bug in it reports a healthy kill rate over mutants that
were never applied. These tests pin the three operators and the sampling
contract; the subprocess/pytest half is exercised by running the script, not
from here.

``scripts/`` is not on ``pythonpath`` (pyproject pins it to ``src``), so the
module is loaded by path rather than imported by name — cheaper than widening
the path for one consumer. It is registered in ``sys.modules`` before being
executed because the script uses ``from __future__ import annotations``, which
makes every annotation a string: ``@dataclass`` then resolves them through
``sys.modules[cls.__module__]``, and an unregistered module fails there.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "mutation_ratchet", REPO_ROOT / "scripts" / "mutation_ratchet.py"
)
assert _SPEC is not None and _SPEC.loader is not None
mutation_ratchet = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mutation_ratchet
_SPEC.loader.exec_module(mutation_ratchet)


# --- operators ---------------------------------------------------------------


@pytest.mark.parametrize(
    "source, expected",
    [
        ("def f(a, b):\n    return a < b\n", "a <= b"),
        ("def f(a, b):\n    return a <= b\n", "a < b"),
        ("def f(a, b):\n    return a > b\n", "a >= b"),
        ("def f(a, b):\n    return a >= b\n", "a > b"),
        ("def f(a, b):\n    return a == b\n", "a != b"),
        ("def f(a, b):\n    return a != b\n", "a == b"),
    ],
)
def test_comparison_operators_are_swapped_to_their_boundary_neighbour(source, expected):
    mutated, _ = mutation_ratchet.apply_mutation(source, 0)
    assert expected in mutated


def test_boolean_operators_flip():
    mutated, description = mutation_ratchet.apply_mutation(
        "def f(a, b):\n    return a and b\n", 0
    )
    assert "a or b" in mutated
    assert "And flip" in description


def test_boolean_constants_flip():
    mutated, description = mutation_ratchet.apply_mutation("x = True\n", 0)
    assert "x = False" in mutated
    assert "True->False" in description


def test_non_boolean_constants_are_left_alone():
    """Arithmetic and string mutants are out of scope: they yield far more
    equivalent mutants per real one, inflating the denominator."""
    source = "x = 42\ny = 'hello'\n"
    assert mutation_ratchet.count_mutations(source) == 0


def test_description_carries_the_line_number():
    _, description = mutation_ratchet.apply_mutation("a = 1\nb = a > 2\n", 0)
    assert description.startswith("L2 ")


# --- indexing contract -------------------------------------------------------


def test_each_index_mutates_exactly_one_site():
    source = "def f(a, b, c):\n    return a < b and c > a\n"
    assert mutation_ratchet.count_mutations(source) == 3
    variants = {mutation_ratchet.apply_mutation(source, i)[0] for i in range(3)}
    assert len(variants) == 3, "each index must produce a distinct mutant"


def test_an_out_of_range_index_applies_nothing():
    """A miss must be skippable rather than counted as a killed mutant."""
    assert mutation_ratchet.apply_mutation("x = True\n", 99) is None


def test_count_matches_the_number_of_applicable_indexes():
    source = "def f(a, b):\n    return (a > b) or (a == b) or True\n"
    total = mutation_ratchet.count_mutations(source)
    applied = [mutation_ratchet.apply_mutation(source, i) for i in range(total)]
    assert all(result is not None for result in applied)
    assert mutation_ratchet.apply_mutation(source, total) is None


# --- sampling ----------------------------------------------------------------


def test_sampling_is_reproducible_for_a_package():
    """A rate is only comparable between commits if the sample is the same one."""
    first = mutation_ratchet.select_mutations("llm/skill", 10)
    second = mutation_ratchet.select_mutations("llm/skill", 10)
    assert [(m.path, m.index) for m in first] == [(m.path, m.index) for m in second]


def test_sampling_differs_between_packages():
    """A shared seed across packages would score the same offsets everywhere."""
    skill = mutation_ratchet.select_mutations("llm/skill", 10)
    prompt = mutation_ratchet.select_mutations("llm/prompt", 10)
    assert [m.index for m in skill] != [m.index for m in prompt]


def test_sample_size_is_capped_by_the_pool():
    sample = mutation_ratchet.select_mutations("llm/skill", 10**6)
    assert 0 < len(sample) < 10**6


# --- floors ------------------------------------------------------------------


def test_every_floor_names_a_real_package_with_mirrored_tests():
    """A floor over a package with no mirrored test dir scores nothing and
    silently reports a pass."""
    for package in mutation_ratchet.FLOORS:
        assert (mutation_ratchet.SRC / package).is_dir(), package
        assert mutation_ratchet.test_target_for(package) is not None, package
