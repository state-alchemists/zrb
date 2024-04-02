import os

import jsons

from zrb.helper.string.conversion import to_boolean

PREFER_MICROSERVICES = to_boolean(os.getenv("PROJECT_PREFER_MICROSERVICES", "0"))

AUTOMATE_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(os.path.dirname(AUTOMATE_DIR))
RESOURCE_DIR = os.path.join(PROJECT_DIR, "src", "kebab-zrb-app-name")
DEPLOYMENT_DIR = os.path.join(RESOURCE_DIR, "deployment")
DEPLOYMENT_TEMPLATE_ENV_FILE_NAME = os.path.join(DEPLOYMENT_DIR, "template.env")
APP_DIR = os.path.join(RESOURCE_DIR, "src")
APP_FRONTEND_DIR = os.path.join(APP_DIR, "frontend")
APP_FRONTEND_BUILD_DIR = os.path.join(APP_FRONTEND_DIR, "build")
APP_TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, "template.env")
LOAD_TEST_DIR = os.path.join(RESOURCE_DIR, "loadtest")
LOAD_TEST_TEMPLATE_ENV_FILE_NAME = os.path.join(RESOURCE_DIR, "template.env")

MODULE_CONFIG_PATH = os.path.join(AUTOMATE_DIR, "config", "modules.json")

with open(MODULE_CONFIG_PATH) as file:
    MODULE_JSON_STR = file.read()
MODULES = jsons.loads(MODULE_JSON_STR)
