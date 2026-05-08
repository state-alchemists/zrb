set -e

if [ -z "$TEST" ]
then
    TEST="$1"
fi

# Lint: pyflakes-class checks (unused imports/vars/redefinitions) on src only.
# F-class catches real bugs without flagging style debt; test/ is not gated yet
# because it carries pre-existing unused-import noise.
flake8 src/zrb --select=F

pytest \
    --ignore-glob="**/template/**" \
    --ignore-glob="**/fastapp_template/**" \
    --ignore="playground" \
    --ignore="llm-challenges" \
    --cov=zrb \
    --cov-config=".coveragerc" \
    --cov-report="html" \
    --cov-report="term-missing:skip-covered" \
    "$TEST"
