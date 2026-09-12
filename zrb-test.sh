set -e

# Targets are the path args (file / dir / file::test). Accept any number of them.
# Back-compat: if none are given but $TEST is set, use $TEST as the single target.
if [ "$#" -eq 0 ] && [ -n "$TEST" ]; then
    set -- "$TEST"
fi

# Lint: pyflakes-class checks (unused imports/vars/redefinitions) on src only.
# F-class catches real bugs without flagging style debt; test/ is not gated yet
# because it carries pre-existing unused-import noise.
flake8 src/zrb --select=F

# Complexity ratchets (mccabe via flake8, true per-function via radon) and the
# private-test-access ratchet now live as pytest tests in test/architecture/ —
# test_complexity_ratchet.py and test_private_test_access_ratchet.py — so a
# violation is a normal pytest failure, not shell output to scroll up for.
# They run as part of the pytest invocation below.

# Static type check. pyright is clean in "standard" mode (pyrightconfig.json);
# keep it that way. Run only on a full pass — it type-checks the whole tree
# regardless of the path args, so gating it per-file would be misleading.
if [ "$#" -eq 0 ]; then
    pyright src/zrb
fi

# Enforce the documented >=90% coverage bar, but only on a FULL run. A scoped run
# (one or more paths passed in) exercises only part of the tree, so a global
# threshold would fail spuriously there.
cov_fail_under=""
if [ "$#" -eq 0 ]; then
    cov_fail_under="--cov-fail-under=90"
fi

# Coverage fragments land in the repo root as gitignored `.coverage.*` files,
# one per xdist worker, and pytest-cov combines whatever it finds there. An
# interrupted run -- or a second run started concurrently -- leaves fragments
# behind, and combining fragments recorded under different settings fails the
# whole command with "Can't combine branch coverage data with statement data"
# after the tests have already passed. Give each run its own data file and
# clear any leftovers first, so the command is hermetic.
rm -f "${PWD}/.coverage" "${PWD}"/.coverage.*
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
