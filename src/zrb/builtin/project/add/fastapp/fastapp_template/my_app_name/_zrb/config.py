import os
import platform

DIR = os.path.dirname(__file__)
APP_DIR = os.path.dirname(DIR)
APP_MODULE_NAME = os.path.basename(APP_DIR)

MICROSERVICES_ENV_VARS = {
    "MY_APP_NAME_MODE": "microservices",
    "MY_APP_NAME_AUTH_BASE_URL": "http://localhost:3002",
}
MONOLITH_ENV_VARS = {
    "MY_APP_NAME_MODE": "monolith",
    "MY_APP_NAME_MODULES": "",
}
TEST_ENV_VARS = {
    "MY_APP_NAME_DB_URL": f"sqlite:///{APP_DIR}/test.db",
    "MY_APP_NAM_AUTH_PRIORITIZE_NEW_SESSION": "1",
}

if platform.system() == "Windows":
    ACTIVATE_VENV_SCRIPT = "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser; . .venv\\Scripts\\Activate"  # noqa
else:
    ACTIVATE_VENV_SCRIPT = ". .venv/bin/activate"
