set -e

if [ -z "$TEST" ]
then
    TEST="$1"
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
    "$TEST"
