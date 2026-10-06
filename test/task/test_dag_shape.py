"""Fitness functions for DAG shape: env/input aggregation must stay linear.

Time budgets are ~100x the measured cost; they catch super-linear growth, not
milliseconds.
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
    """Two tasks per level, each depending on both tasks of the level above."""
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
    """Visiting each node once means each env is contributed once."""
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
    """Upstream-first ordering across a diamond: `sink`'s `PORT` beats `shared`'s."""
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
    """Aggregation reads the graph every time, so nothing can go stale."""
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
