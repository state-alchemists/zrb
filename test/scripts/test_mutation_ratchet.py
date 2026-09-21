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
import os
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

# The ratchet refuses to run without POSIX process groups, so the tests that
# drive its cleanup or its entry point have nothing to assert elsewhere.
posix_only = pytest.mark.skipif(
    not hasattr(os, "killpg"), reason="the ratchet is POSIX-only by refusal"
)

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


def test_a_chained_comparison_keeps_the_rest_of_the_chain():
    """Replacing the whole ``ops`` list drops the trailing comparators, turning
    ``a < b < c`` into ``a <= b`` -- a mutant that no longer tests one site."""
    mutated, _ = mutation_ratchet.apply_mutation(
        "def f(a, b, c):\n    return a < b < c\n", 0
    )
    assert "a <= b < c" in mutated


# --- run guards --------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "-1"])
def test_a_non_positive_mutant_count_is_rejected(value):
    with pytest.raises(Exception):
        mutation_ratchet.positive_int(value)


class _FakePytest:
    """A pytest invocation that exits with *returncode* without running."""

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def communicate(self, timeout=None):
        return "", ""


def _fake_pytest(monkeypatch, returncode: int) -> None:
    monkeypatch.setattr(
        mutation_ratchet.subprocess, "Popen", lambda *a, **k: _FakePytest(returncode)
    )


def test_a_pytest_run_that_never_ran_stops_the_ratchet(monkeypatch, tmp_path):
    """Exit code 5 is "no tests collected". Treating it as a test failure counts
    every mutant killed, so a mistargeted run reports a perfect rate."""
    _fake_pytest(monkeypatch, 5)
    with pytest.raises(mutation_ratchet.RatchetError):
        mutation_ratchet.run_tests(tmp_path)


@pytest.mark.parametrize("code, survived", [(0, True), (1, False)])
def test_pass_is_a_survivor_and_failure_is_a_kill(
    monkeypatch, tmp_path, code, survived
):
    _fake_pytest(monkeypatch, code)
    assert mutation_ratchet.run_tests(tmp_path) is survived


def test_a_red_baseline_stops_the_package_before_anything_is_mutated(monkeypatch):
    """Every mutant scores as killed against an already-failing suite, which is
    the one way this ratchet reports a perfect rate over no signal."""
    monkeypatch.setattr(mutation_ratchet, "run_tests", lambda target: False)
    written = []
    monkeypatch.setattr(
        mutation_ratchet.Path, "write_text", lambda self, *a, **k: written.append(self)
    )

    with pytest.raises(mutation_ratchet.RatchetError):
        mutation_ratchet.score_package("llm/skill", 1, verbose=False)
    assert written == []


def test_uncommitted_mirrored_tests_count_as_dirty():
    """The tests are what the score is measured against, so an uncommitted
    assertion raises the rate for work that is not in the tree yet."""
    probe = REPO_ROOT / "test" / "llm" / "skill" / "ratchet_dirty_probe.txt"
    probe.write_text("")
    try:
        assert any(
            "ratchet_dirty_probe" in p
            for p in mutation_ratchet.dirty_paths(["llm/skill"])
        )
    finally:
        probe.unlink()


def test_a_baseline_that_hangs_is_reported_not_raised(monkeypatch):
    """A timeout is a kill for a mutant but not for the baseline, where it means
    the measurement never started."""

    def hang(target):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(mutation_ratchet, "run_tests", hang)
    with pytest.raises(mutation_ratchet.RatchetError):
        mutation_ratchet.score_package("llm/skill", 1, verbose=False)


# --- floors ------------------------------------------------------------------


@pytest.mark.parametrize(
    "killed, scored, floor, cleared",
    [
        (16, 31, 52, False),  # 51.6%, which rounds up into its own floor
        (52, 100, 52, True),
        (51, 100, 52, False),
    ],
)
def test_the_floor_is_compared_as_a_ratio_not_a_rounded_percentage(
    killed, scored, floor, cleared
):
    assert mutation_ratchet.meets_floor(killed, scored, floor) is cleared


# --- process cleanup ---------------------------------------------------------


def _alive(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


@posix_only
def test_a_timed_out_run_takes_its_descendants_with_it():
    """Killing only the direct child leaves a grandchild running pytest against
    source the next mutant is rewriting."""
    spawner = (
        "import subprocess, sys, time;"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
        "print(child.pid, flush=True);"
        "time.sleep(60)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", spawner],
        stdout=subprocess.PIPE,
        text=True,
        **mutation_ratchet.OWN_PROCESS_GROUP,
    )
    grandchild = None
    try:
        assert process.stdout is not None
        grandchild = int(process.stdout.readline())

        mutation_ratchet.kill_process_tree(process)

        assert not _alive(process.pid)
        assert not _alive(grandchild)
    finally:
        for pid in (process.pid, grandchild):
            if pid is not None and _alive(pid):
                psutil.Process(pid).kill()
        if process.stdout is not None:
            process.stdout.close()


@posix_only
def test_a_package_that_scores_no_mutants_fails(monkeypatch, capsys):
    """A floor over nothing is a floor nothing can breach: if discovery stops
    finding sites, the ratchet must not report a pass."""
    monkeypatch.setattr(mutation_ratchet, "dirty_paths", lambda packages: [])
    monkeypatch.setattr(mutation_ratchet, "score_package", lambda *a, **k: (0, 0))
    monkeypatch.setattr(sys, "argv", ["mutation_ratchet.py", "llm/skill"])

    assert mutation_ratchet.main() == 1
    assert "no mutants scored" in capsys.readouterr().out


@posix_only
def test_descendants_die_once_the_direct_child_is_already_gone():
    """A timeout does not mean pytest is still running.

    A descendant holding the inherited pipe keeps ``communicate`` waiting long
    after pytest exits, and by then its children are reparented -- so a walk
    down from the pid finds nothing and the survivor keeps running against
    source the next mutant rewrites.
    """
    spawner = (
        "import subprocess, sys;"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
        "print(child.pid, flush=True)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", spawner],
        stdout=subprocess.PIPE,
        text=True,
        **mutation_ratchet.OWN_PROCESS_GROUP,
    )
    grandchild = None
    try:
        assert process.stdout is not None
        grandchild = int(process.stdout.readline())
        process.wait()

        assert process.poll() is not None, "the direct child must be gone already"
        assert _alive(grandchild), "the descendant must outlive it"

        mutation_ratchet.kill_process_tree(process)

        assert not _alive(grandchild)
    finally:
        if grandchild is not None and _alive(grandchild):
            psutil.Process(grandchild).kill()
        if process.stdout is not None:
            process.stdout.close()


def test_a_source_file_that_does_not_parse_stops_the_run(monkeypatch):
    """Dropping its sites shrinks the denominator, and a smaller denominator
    reads as a cleaner package."""

    def unparsable(source):
        raise SyntaxError("invalid syntax")

    monkeypatch.setattr(mutation_ratchet, "count_mutations", unparsable)
    with pytest.raises(mutation_ratchet.RatchetError):
        mutation_ratchet.select_mutations("llm/skill", 10)


def test_the_ratchet_refuses_to_run_without_process_groups(monkeypatch, capsys):
    """Without them a timed-out run can leave pytest alive against source the
    next mutant rewrites, so the number it produces means nothing."""
    monkeypatch.delattr(os, "killpg", raising=False)
    monkeypatch.setattr(sys, "argv", ["mutation_ratchet.py", "llm/skill"])

    assert mutation_ratchet.main() == 1
    assert "WSL" in capsys.readouterr().err
