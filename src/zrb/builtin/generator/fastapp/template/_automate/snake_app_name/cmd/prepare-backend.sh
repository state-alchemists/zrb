PYTHONUNBUFFERED=1

if [ ! -d venv ]
then
  echo "Init venv"
  python -m venv venv
fi
echo "Activate venv"
source venv/bin/activate

echo "Install packages"
pip install -r requirements.txt

