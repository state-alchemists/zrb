PYTHONUNBUFFERED=1
echo "Install packages"
pip install -r requirements.txt

echo "Start app"
uvicorn main:app --host {{env.get("APP_HOST", "0.0.0.0")}} --port {{env.get("APP_PORT", "8080")}}
