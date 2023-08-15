PYTHONUNBUFFERED=1
echo "Activate virtual environment"
source .venv/bin/activate

echo "Publish"
flit publish --repository {{input.snake_zrb_package_name_repo}}
