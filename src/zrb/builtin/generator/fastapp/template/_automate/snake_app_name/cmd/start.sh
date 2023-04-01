PYTHONUNBUFFERED=1
echo "Activate venv"
source venv/bin/activate

echo "Start app"
uvicorn main:app --host {{env.get("APP_HOST", "0.0.0.0")}} --port {{env.get("APP_PORT", "8080")}} {{ "--reload" if util.to_boolean(env.get("APP_RELOAD", "true")) else "" }}
