"""Mutation-kill-rate ratchet: does the suite *assert*, or only *execute*?

Line coverage answers "was this line run". It cannot answer "would a test have
noticed if the line were wrong", and the gap between those is where bugs ship.

Each mutant runs only its package's mirrored tests, so the rate answers "is
*this package* asserted on" rather than "did the system notice somewhere" --
a harder question than a whole-suite pass, and a lower number.

The behavioural twin of the shape ratchets in ``test/architecture/``, under the
same rule: ``FLOORS`` **only ever goes up**. Raising one needs nothing but the
diff that earns it; lowering one needs a reason in the same diff.

A script rather than a pytest test because a pass is minutes, not seconds -- it
is run on demand, not from the per-commit gate. See ADR-0097 for the
measurements and for why ``mutmut``/``cosmic-ray`` do not fit this layout.

Usage::

    python scripts/mutation_ratchet.py                 # every package in FLOORS
    python scripts/mutation_ratchet.py llm/skill       # just one
    python scripts/mutation_ratchet.py --mutants 40    # wider sample

Exit code is non-zero if any package falls below its floor.
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "zrb"
TESTS = REPO_ROOT / "test"

# Per-package kill-rate floors, as a percentage. Floors that only go UP.
#
# These four are where a wrong boolean is most expensive: process teardown,
# prompt assembly, skill discovery. A package belongs here once it has a
# measured rate; a speculative floor of 0 asserts nothing.
#
# Baseline at 25 mutants each: task/base 56%, util/cmd 35%, llm/skill 60%,
# llm/prompt 56%. Each floor sits a few points under its baseline, unlike the
# line-count budgets which are pinned exact -- an edit to a package shifts which
# mutation sites get drawn, so the rate moves a little with no test changing.
# The margin absorbs that drift; it is not slack for new untested code.
FLOORS: dict[str, int] = {
    "task/base": 50,
    "util/cmd": 30,
    "llm/skill": 55,
    "llm/prompt": 50,
}

# An exhaustive pass over four packages is hours, so this samples. The seed is
# fixed and the count explicit so a rate is reproducible across runs.
DEFAULT_MUTANTS_PER_PACKAGE = 25
SEED = 20260918

# A hang is a detection, not a survival (pytest-timeout fails it), so this only
# has to exceed a healthy run of one package's tests.
MUTANT_TIMEOUT_SECONDS = 600

PYTEST_PASSED = 0
PYTEST_FAILED = 1


class PytestRunError(RuntimeError):
    """The run cannot be scored: pytest failed to run, or the baseline is red."""


@dataclass(frozen=True)
class Mutation:
    """One applied source edit, addressed by its index in the file's mutation order."""

    path: Path
    index: int
    description: str


class _Mutator(ast.NodeTransformer):
    """Applies the single mutation at ``target`` and records what it did.

    Comparison swap, boolean-operator flip, boolean-constant flip. Arithmetic and
    string operators are excluded: they yield far more equivalent mutants per
    real one here, inflating the denominator without adding signal.

    A chained comparison (``a < b < c``) offers one site, its leading operator;
    the rest of the chain is left intact. Per-operator sites would be the fuller
    treatment, and are worth adding if a survivor ever turns out to hide behind
    one.
    """

    def __init__(self, target: int) -> None:
        self.target = target
        self.seen = 0
        self.applied: str | None = None

    def _take(self, node: ast.AST, description: str) -> bool:
        hit = self.seen == self.target
        if hit:
            self.applied = f"L{getattr(node, 'lineno', 0)} {description}"
        self.seen += 1
        return hit

    _SWAP = {
        ast.Lt: ast.LtE,
        ast.LtE: ast.Lt,
        ast.Gt: ast.GtE,
        ast.GtE: ast.Gt,
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
    }

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        op = type(node.ops[0])
        replacement = self._SWAP.get(op)
        if replacement and self._take(node, f"{op.__name__}->{replacement.__name__}"):
            node.ops[0] = replacement()
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        name = type(node.op).__name__
        if self._take(node, f"{name} flip"):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool) and self._take(
            node, f"{node.value}->{not node.value}"
        ):
            return ast.copy_location(ast.Constant(not node.value), node)
        return node


def count_mutations(source: str) -> int:
    """How many mutation sites *source* offers."""
    mutator = _Mutator(target=-1)
    mutator.visit(ast.parse(source))
    return mutator.seen


def apply_mutation(source: str, index: int) -> tuple[str, str] | None:
    """Return ``(mutated_source, description)``, or ``None`` if *index* missed."""
    mutator = _Mutator(target=index)
    tree = ast.fix_missing_locations(mutator.visit(ast.parse(source)))
    if mutator.applied is None:
        return None
    return ast.unparse(tree), mutator.applied


def select_mutations(package: str, sample_size: int) -> list[Mutation]:
    """A reproducible sample of mutation sites across *package*'s modules.

    Sites are pooled across the whole package before sampling so a 900-line
    module does not crowd out a 40-line one purely by offering more sites; the
    sort keeps the pool order independent of filesystem iteration order.
    """
    pool: list[Mutation] = []
    for path in sorted((SRC / package).rglob("*.py")):
        try:
            total = count_mutations(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        pool.extend(Mutation(path, i, "") for i in range(total))
    rng = random.Random(f"{SEED}:{package}")
    return rng.sample(pool, min(sample_size, len(pool)))


def test_target_for(package: str) -> Path | None:
    """The mirrored test directory for *package*, if one exists.

    ``test/`` mirrors ``src/zrb/``. Running only the mirrored directory is both
    fast and the sharper question: a mutant killed by an unrelated integration
    test is not evidence that *this* package is asserted on.
    """
    candidate = TESTS / package
    return candidate if candidate.is_dir() else None


def kill_process_tree(process: subprocess.Popen) -> None:
    """SIGKILL *process* and everything it spawned, then reap them.

    On timeout ``subprocess.run`` kills the direct child and nothing below it.
    This suite starts real shells, so a survivor keeps running pytest against
    source the next mutant is already rewriting -- the results it produces
    belong to no measurement at all.

    Descendants are collected before the parent dies, because reparenting makes
    them unreachable from its pid afterwards.
    """
    try:
        parent = psutil.Process(process.pid)
        doomed = parent.children(recursive=True) + [parent]
    except psutil.NoSuchProcess:
        return
    for victim in doomed:
        try:
            victim.kill()
        except psutil.NoSuchProcess:
            continue
    psutil.wait_procs(doomed, timeout=30)
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass  # unreapable child; the caller's timeout is already the story


def run_tests(target: Path) -> bool:
    """True if the suite passed (mutant survived), False if it failed (killed).

    Any other exit code means pytest never got as far as running the tests --
    a collection error, a usage error, an empty target. Counting those as kills
    is what would let a broken environment report a perfect rate, so they stop
    the run instead.

    A timeout propagates as ``TimeoutExpired``, but only once the process tree
    is down.
    """
    with subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pytest",
            str(target),
            "-x",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=MUTANT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            kill_process_tree(process)
            raise
    if process.returncode not in (PYTEST_PASSED, PYTEST_FAILED):
        raise PytestRunError(
            f"pytest exited {process.returncode} on {target}\n"
            f"{stdout[-2000:]}{stderr[-2000:]}"
        )
    return process.returncode == PYTEST_PASSED


def meets_floor(killed: int, scored: int, floor: int) -> bool:
    """Whether *killed* of *scored* clears *floor*, as an exact ratio.

    Rounding the percentage first passes a package that is under its floor:
    16/31 is 51.6%, which rounds to the 52 it has to beat.
    """
    return 100 * killed >= floor * scored


def score_package(package: str, sample_size: int, verbose: bool) -> tuple[int, int]:
    """Run every sampled mutant for *package*; return ``(killed, scored)``.

    A baseline run comes first, because a package whose tests already fail marks
    every mutant killed -- the one way this ratchet can report a perfect rate
    over no signal at all.

    The restore is in a ``finally`` so an exception or a timeout cannot leave a
    mutation in the working tree.
    """
    target = test_target_for(package)
    if target is None:
        print(f"  ! no mirrored test dir for {package}, skipping")
        return 0, 0
    try:
        baseline_passed = run_tests(target)
    except subprocess.TimeoutExpired as error:
        raise PytestRunError(
            f"{target} did not finish within {MUTANT_TIMEOUT_SECONDS}s before "
            "any mutation was applied."
        ) from error
    if not baseline_passed:
        raise PytestRunError(
            f"{target} already fails before any mutation is applied; every "
            "mutant would score as killed. Fix the suite first."
        )
    killed = scored = 0
    for mutation in select_mutations(package, sample_size):
        original = mutation.path.read_text(encoding="utf-8")
        result = apply_mutation(original, mutation.index)
        if result is None:
            continue
        mutated, description = result
        try:
            mutation.path.write_text(mutated, encoding="utf-8")
            try:
                survived = run_tests(target)
            except subprocess.TimeoutExpired:
                survived = False
        finally:
            mutation.path.write_text(original, encoding="utf-8")
        scored += 1
        killed += not survived
        if verbose or survived:
            verdict = "SURVIVED" if survived else "killed  "
            rel = mutation.path.relative_to(REPO_ROOT)
            print(f"  {verdict} {rel}:{description}")
    return killed, scored


def dirty_paths(packages: list[str]) -> list[str]:
    """Uncommitted changes under *packages*, source and mirrored tests alike.

    ``ast.unparse`` reproduces the code but drops every comment, and the restore
    in :func:`score_package` cannot cover a SIGKILL. Refusing to start on a dirty
    tree makes ``git checkout`` a complete recovery for that case -- cheaper than
    a backup directory, and it cannot go stale.

    The mirrored tests are checked for a second reason: they are what the score
    is measured against, so an uncommitted assertion raises the rate for work
    that is not in the tree yet.
    """
    targets = [str(SRC / package) for package in packages]
    targets += [str(TESTS / package) for package in packages]
    result = subprocess.run(
        ["git", "status", "--porcelain", "--"] + targets,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []  # not a git checkout; nothing to protect, nothing to promise
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, got {number}")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "packages",
        nargs="*",
        help="package paths relative to src/zrb (default: every key in FLOORS)",
    )
    parser.add_argument(
        "--mutants",
        type=positive_int,
        default=DEFAULT_MUTANTS_PER_PACKAGE,
        help=f"mutants sampled per package (default: {DEFAULT_MUTANTS_PER_PACKAGE})",
    )
    parser.add_argument(
        "--json", type=Path, help="also write the per-package results here"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print killed mutants too"
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="run even with uncommitted changes under the target packages",
    )
    args = parser.parse_args()

    packages = args.packages or list(FLOORS)
    unknown = [p for p in packages if p not in FLOORS]
    if unknown:
        parser.error(f"no floor defined for: {', '.join(unknown)}")

    dirty = dirty_paths(packages)
    if dirty and not args.allow_dirty:
        print("Uncommitted changes under the target packages:")
        for path in dirty:
            print(f"  {path}")
        print(
            "\nMutants are written with ast.unparse, which drops comments. Commit "
            "or stash first so `git checkout` can recover the tree if this run is "
            "killed outright; --allow-dirty accepts that risk."
        )
        return 1

    started = time.monotonic()
    results: dict[str, dict[str, int]] = {}
    failures: list[str] = []

    for package in packages:
        print(f"\n{package} (floor {FLOORS[package]}%)")
        try:
            killed, scored = score_package(package, args.mutants, args.verbose)
        except PytestRunError as error:
            print(f"  ! {error}")
            return 1
        if scored == 0:
            # A floor over nothing is a floor nothing can breach.
            print("  -> no mutants scored")
            failures.append(f"{package}: no mutants scored")
            continue
        rate = round(100 * killed / scored)
        results[package] = {"killed": killed, "scored": scored, "rate": rate}
        cleared = meets_floor(killed, scored, FLOORS[package])
        status = "OK" if cleared else "BELOW FLOOR"
        print(f"  -> {killed}/{scored} killed = {rate}%  [{status}]")
        if not cleared:
            failures.append(
                f"{package}: {killed}/{scored} (~{rate}%) < {FLOORS[package]}%"
            )

    elapsed = time.monotonic() - started
    total_killed = sum(r["killed"] for r in results.values())
    total_scored = sum(r["scored"] for r in results.values())
    overall = round(100 * total_killed / total_scored) if total_scored else 0
    print(f"\noverall: {total_killed}/{total_scored} killed = {overall}%")
    print(f"elapsed: {elapsed:.0f}s")

    if args.json:
        args.json.write_text(
            json.dumps({"packages": results, "overall": overall}, indent=2),
            encoding="utf-8",
        )

    if failures:
        print("\nBelow floor:")
        for failure in failures:
            print(f"  {failure}")
        print(
            "\nA survivor is a line the suite runs but never asserts on. Add the "
            "missing assertion, or -- if the mutant is genuinely equivalent -- "
            "say so in the diff that lowers the floor."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
