set -e

# Targets are path args (file / dir / file::test). With none, $TEST is used if set.
if [ "$#" -eq 0 ] && [ -n "$TEST" ]; then
    set -- "$TEST"
fi

# Pyflakes-class checks only (unused imports/vars, redefinitions); src only,
# test/ carries unused-import noise. Complexity and other shape ratchets run as
# pytest tests under test/architecture/.
flake8 src/zrb --select=F

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

ZRB_INIT_SCRIPTS="" pytest \
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
