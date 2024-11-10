set -e

if [ -z "$TEST" ]
then
    TEST="$1"
fi

pytest -vv \
    --ignore-glob="**/template/**" \
    --ignore="playground" \
    --cov=zrb \
    --cov-config=".coveragerc" \
    --cov-report="html" \
    --cov-report="term" \
    --cov-report="term-missing" \
    "$TEST"
