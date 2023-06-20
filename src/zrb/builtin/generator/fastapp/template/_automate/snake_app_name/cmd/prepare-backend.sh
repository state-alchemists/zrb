PYTHONUNBUFFERED=1

if [ ! -d .venv ]
then
  echo "Init virtual environment"
  python -m venv .venv
fi
echo "Activate virtual environment"
source .venv/bin/activate

echo "Install packages"
pip install -r requirements.txt

