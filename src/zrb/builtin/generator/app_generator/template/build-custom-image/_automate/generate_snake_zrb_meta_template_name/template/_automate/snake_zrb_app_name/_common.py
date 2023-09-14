from zrb import BoolInput, StrInput
import os

###############################################################################
# Constants
###############################################################################

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
RESOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'kebab-zrb-app-name')
DEPLOYMENT_DIR = os.path.join(RESOURCE_DIR, 'deployment')
DEPLOYMENT_TEMPLATE_ENV_FILE_NAME = os.path.join(
    DEPLOYMENT_DIR, 'template.env'
)
APP_DIR = os.path.join(RESOURCE_DIR, 'src')
APP_TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, 'template.env')

###############################################################################
# Input Definitions
###############################################################################

local_input = BoolInput(
    name='local-kebab-zrb-app-name',
    description='Use "kebab-zrb-app-name" on local machine',
    prompt='Use "kebab-zrb-app-name" on local machine?',
    default=True
)

https_input = BoolInput(
    name='kebab-zrb-app-name-https',
    description='Whether "kebab-zrb-app-name" run on HTTPS',
    prompt='Is "kebab-zrb-app-name" run on HTTPS?',
    default=False
)

host_input = StrInput(
    name='kebab-zrb-app-name-host',
    description='Hostname of "kebab-zrb-app-name"',
    prompt='Hostname of "kebab-zrb-app-name"',
    default='localhost'
)
