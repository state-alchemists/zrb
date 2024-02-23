command_exists() {
    command -v "$1" &> /dev/null
}

if ! command_exists poetry
then
    echo 'Install poetry'
    pip install --upgrade pip setuptools
    pip install "poetry==1.7.1"
fi
if [ ! -d .venv ]
then
  echo "Init virtual environment"
  python -m venv .venv
fi
echo "Activate virtual environment"
source .venv/bin/activate
