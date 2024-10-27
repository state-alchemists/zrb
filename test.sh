set -e
pytest -vv \
    --ignore-glob="**/template/**" \
    --ignore="playground" \
    --cov=zrb \
    --cov-config=".coveragerc" \
    --cov-report="html" \
    --cov-report="term" \
    --cov-report="term-missing" \
    "${1}"

echo "Hello world"