set -e

if [ -z "$TEST" ]
then
    TEST="$1"
fi

# Lint: pyflakes-class checks (unused imports/vars/redefinitions) on src only.
# F-class catches real bugs without flagging style debt; test/ is not gated yet
# because it carries pre-existing unused-import noise.
flake8 src/zrb --select=F

# Enforce the documented >=90% coverage bar, but only on a FULL run. A scoped run
# (a single file/dir passed as $TEST) exercises only part of the tree, so a global
# threshold would fail spuriously there.
cov_fail_under=""
if [ -z "$TEST" ]; then
    cov_fail_under="--cov-fail-under=90"
fi

pytest \
    --ignore-glob="**/template/**" \
    --ignore-glob="**/fastapp_template/**" \
    --ignore="playground" \
    --ignore="llm-challenges" \
    --cov=zrb \
    --cov-config=".coveragerc" \
    --cov-report="html" \
    --cov-report="term-missing:skip-covered" \
    ${cov_fail_under} \
    "$TEST"
