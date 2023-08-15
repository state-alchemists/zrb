PYTHONUNBUFFERED=1
echo "Activate virtual environment"
source .venv/bin/activate

echo "Git add"
git add . -A

echo "Build"
flit build
