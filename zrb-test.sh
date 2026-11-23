set -e

# Targets are path args (file / dir / file::test). With none, $TEST is used if set.
if [ "$#" -eq 0 ] && [ -n "$TEST" ]; then
    set -- "$TEST"
fi

# `./zrb-test.sh eval` runs the paid agent evaluation: 16 fixture repositories,
# each one a real `zrb llm chat` turn scored by behavior (does the module import,
# does the suite pass) rather than by prose. It is opt-in because it spends
# money and time, so it is its own mode instead of part of the default run:
# no coverage, no pyright, one worker (the model API is the bottleneck).
# Model selection: `LLM_EVAL_MODEL=deepseek:deepseek-chat ./zrb-test.sh eval`.
# Extra args reach pytest, e.g. `./zrb-test.sh eval -k rename`.
if [ "$#" -gt 0 ] && [ "$1" = "eval" ]; then
    shift
    LLM_EVAL_RUN=1 PYTEST_XDIST_AUTO_NUM_WORKERS=1 exec pytest \
        -n 0 \
        -q \
        -p no:cacheprovider \
        test/eval \
        "$@"
fi

# `./zrb-test.sh ratchet` is the quick loop to use while changing code: the
# architecture ratchets are ordinary pytest tests under test/architecture/, so
# this is a name for a path, not a second mode. A scoped run already skips
# pyright and the coverage floor below, and the flake8 pass above still runs.
if [ "$#" -gt 0 ] && [ "$1" = "ratchet" ]; then
    shift
    set -- test/architecture "$@"
fi

# Pyflakes-class checks only (unused imports/vars, redefinitions); src only,
# test/ carries unused-import noise. Complexity and other shape ratchets run as
# pytest tests under test/architecture/.
flake8 src/zrb --select=F

# The house format, in check mode — the same flags `zrb code format` runs. It
# is checked because the facade budgets are pinned to exact line counts: an
# unformatted diff moves a number that should only move when the code does.
# Both tools are development dependencies, so `poetry install` brings them;
# name the fix rather than fail mid-gate as `command not found`.
for tool in isort black; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "zrb-test.sh: $tool is missing, and the gate checks the house format." >&2
        echo "Install the development dependencies: poetry install" >&2
        exit 1
    fi
done
isort . --check-only --profile black --force-grid-wrap 0 \
    --skip-glob 'llm-challenges/**' --skip-glob '.claude/**' \
    --skip-glob '.zrb/**' --skip-glob '.venv/**'
black --check . --extend-exclude 'llm-challenges'

# pyright checks the whole tree regardless of path args, so full runs only.
if [ "$#" -eq 0 ]; then
    pyright src/zrb
fi

# The >=95% coverage bar (ADR-0034) applies to full runs only; a scoped run
# covers part of the tree and would fail spuriously.
cov_fail_under=""
if [ "$#" -eq 0 ]; then
    cov_fail_under="--cov-fail-under=95"
fi

# Per-run coverage fragments: pytest-cov combines every `.coverage.*` it finds,
# so a shared directory lets an interrupted or concurrent run break this one
# ("Can't combine branch coverage data with statement data"). The HTML report
# stays at ./htmlcov so it is easy to find; concurrent runs may interleave it.
COVERAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${COVERAGE_DIR}"' EXIT
export COVERAGE_FILE="${COVERAGE_DIR}/.coverage"

# Environment hygiene is the suite's business, not the shell's: `pytest_configure`
# in test/conftest.py removes the whole config namespace before collection, so no
# variable a developer exported — `ZRB_INIT_SCRIPTS` included — can reach a test.
# That holds for every entry point (this script, a bare `pytest`, and each xdist
# worker), which is why nothing is neutralized here.
# `-n auto` reads this; one per core (10 here) at ~300 MB each ran a 6.6 GB WSL
# out of memory, and the OOM killer took the zrb chat beside it. A bare
# `pytest -n auto` is not capped: export the variable for that.
export PYTEST_XDIST_AUTO_NUM_WORKERS="${PYTEST_XDIST_AUTO_NUM_WORKERS:-4}"
pytest \
    -n auto \
    --ignore-glob="**/template/**" \
    --ignore-glob="**/fastapp_template/**" \
    --ignore="playground" \
    --ignore="llm-challenges" \
    --cov=zrb \
    --cov-config=".coveragerc" \
    --cov-report="html" \
    --cov-report="term-missing:skip-covered" \
    ${cov_fail_under} \
    "$@"
