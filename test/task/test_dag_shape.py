"""Fitness functions for DAG *shape*, not DAG behavior.

Every other ratchet in this repo measures static shape — parameter counts,
file lines, cyclomatic complexity, private access. None of them measures what
the engine does as a graph grows, and that gap hid a real defect: `.envs` and
`.inputs` recursed through each other, re-deriving each node's whole closure
once per incoming edge. Cost was O(n^3) on a chain and O(2**depth) on a
diamond, and `runner/cli.py` reads `task.inputs` before a task even starts, so
`zrb <task>` on a 41-task lattice never returned.

It stayed hidden because zrb's own `zrb_init.py` tops out at 97 tasks and
depth 6 — dogfooding does not reach the shapes users build.

The time budgets here are deliberately loose (~100x the measured cost on a
slow CI box). They exist to catch a return to super-linear growth, not to
police milliseconds; a genuine slowdown will blow past them by orders of
magnitude, which is exactly what the original defect did.
"""

import time

from zrb.env.env import Env
from zrb.input.str_input import StrInput
from zrb.task.task import Task


def _chain(depth: int) -> Task:
    """A linear pipeline `depth` tasks long, each with one distinct input."""
    prev: Task | None = None
    for i in range(depth):
        task = Task(name=f"t{i}", input=StrInput(f"i{i}", default="x"))
        if prev is not None:
            task << prev
        prev = task
    assert prev is not None
    return prev


def _lattice(levels: int) -> Task:
    """Two tasks per level, each depending on *both* tasks of the level above.

    The shape a monorepo produces when a shared stage fans out and back in.
    It is what turns an un-memoized closure walk exponential.
    """
    prev = [
        Task(name="a0", input=StrInput("a0", default="x"), env=Env("A0")),
        Task(name="b0", input=StrInput("b0", default="x"), env=Env("B0")),
    ]
    for i in range(1, levels):
        current = [
            Task(name=f"a{i}", input=StrInput(f"a{i}", default="x"), env=Env(f"A{i}")),
            Task(name=f"b{i}", input=StrInput(f"b{i}", default="x"), env=Env(f"B{i}")),
        ]
        for task in current:
            task << prev
        prev = current
    sink = Task(name="sink")
    sink << prev
    return sink


def test_diamond_dag_input_aggregation_does_not_blow_up():
    """22 levels took 13 seconds before the walk became single-pass."""
    sink = _lattice(22)

    start = time.perf_counter()
    inputs = sink.inputs
    elapsed = time.perf_counter() - start

    assert len(inputs) == 44
    assert elapsed < 1.0, f"one .inputs read on a 45-task lattice took {elapsed:.2f}s"


def test_diamond_dag_env_aggregation_returns_one_entry_per_env():
    """Visiting each node once means each env is contributed once.

    The recursive form re-appended a shared ancestor's envs per branch, so
    this list held 131,070 entries for 32 distinct envs.
    """
    sink = _lattice(16)

    envs = sink.envs

    assert len(envs) == 32
    assert len({id(env) for env in envs}) == 32


def test_deep_chain_input_aggregation_stays_within_budget():
    sink = _chain(400)

    start = time.perf_counter()
    inputs = sink.inputs
    elapsed = time.perf_counter() - start

    assert len(inputs) == 400
    assert elapsed < 5.0, f"one .inputs read on a 400-deep chain took {elapsed:.2f}s"


def test_a_chain_deeper_than_the_interpreter_stack_still_resolves():
    """The walk is iterative; the recursive form died past ~450 levels."""
    sink = _chain(2000)

    assert len(sink.inputs) == 2000


def test_a_task_overrides_an_env_its_transitive_upstream_declares():
    """Upstream-first ordering, across a diamond.

    `a` and `b` both depend on `shared`, and `sink` on both. `sink` declaring
    `PORT` must beat `shared` declaring it — under the old recursive form the
    second branch re-appended `shared`'s copy last, and `shared` won.
    """
    shared = Task(name="shared", env=Env("PORT", default="1111", link_to_os=False))
    left = Task(name="left")
    right = Task(name="right")
    left << shared
    right << shared
    sink = Task(name="sink", env=Env("PORT", default="9999", link_to_os=False))
    sink << [left, right]

    names = [env.name for env in sink.envs]

    assert names.count("PORT") == 2
    assert names[-1] == "PORT"
    assert sink.envs[-1].default == "9999"


def test_rewiring_after_a_read_is_reflected():
    """Aggregation reads the graph every time, so nothing can go stale.

    Reading first and wiring second is the order a cache would get wrong; it
    stays pinned so reintroducing one has to face this test.
    """
    downstream = Task(name="downstream", input=StrInput("own", default="x"))
    upstream = Task(name="upstream", input=StrInput("added", default="x"))
    assert [i.name for i in downstream.inputs] == ["own"]

    downstream << upstream

    assert [i.name for i in downstream.inputs] == ["added", "own"]


def test_a_cycle_created_after_a_successful_read_is_still_detected():
    """The walk carries its own on-path set, replacing the re-entrancy flags."""
    first = Task(name="first", input=StrInput("a", default="x"))
    second = Task(name="second", input=StrInput("b", default="x"))
    first << second
    assert len(first.inputs) == 2

    second << first  # closes the loop

    try:
        _ = first.inputs
    except ValueError as error:
        assert "Circular task dependency detected" in str(error)
    else:
        raise AssertionError("a cycle introduced after a cached read went undetected")
