import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
RESOURCE_DIR = os.path.join(PROJECT_DIR, "src", "kebab-zrb-app-name")
DEPLOYMENT_DIR = os.path.join(RESOURCE_DIR, "deployment")
DEPLOYMENT_TEMPLATE_ENV_FILE_NAME = os.path.join(DEPLOYMENT_DIR, "template.env")
APP_DIR = os.path.join(RESOURCE_DIR, "src")
APP_TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, "template.env")
