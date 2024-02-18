if [ ! -d .venv ]
then
  echo "Init virtual environment"
  python -m venv .venv
  source .venv/bin/activate
  echo "Upgrade Pip"
  pip install -U pip
  echo "Install Poetry"
  pip install "poetry==1.7.1"
fi
echo "Activate virtual environment"
source .venv/bin/activate