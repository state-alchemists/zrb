PYTHONUNBUFFERED=1
echo "Activate virtual environment"
source .venv/bin/activate

echo "Install symlink"
flit install --symlink
