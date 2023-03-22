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

echo "Start app"
uvicorn main:app --host {{env.get("APP_HOST", "0.0.0.0")}} --port {{env.get("APP_PORT", "8080")}}
