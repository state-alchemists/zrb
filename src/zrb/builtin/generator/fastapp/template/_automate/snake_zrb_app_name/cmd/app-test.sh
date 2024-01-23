export PYTHONUNBUFFERED=1
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
cd src
echo "Activate virtual environment"
source .venv/bin/activate

cd ..
pytest \
    --ignore=postgres-data \
    --cov=src \
    --cov-report html \
    --cov-report term \
    --cov-report term-missing {{input.snake_zrb_app_name_test}}