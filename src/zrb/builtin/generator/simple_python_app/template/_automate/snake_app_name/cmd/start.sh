PYTHONUNBUFFERED=1

if [ ! -d venv ]
then
  echo "Init venv"
  python -m venv venv
fi

echo "Install packages"
pip install -r requirements.txt

echo "Start app"
python main.py
