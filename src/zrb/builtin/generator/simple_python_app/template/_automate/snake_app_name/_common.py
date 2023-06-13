from zrb import BoolInput, StrInput
import os

###############################################################################
# Constants
###############################################################################

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
RESOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'kebab-app-name')
DEPLOYMENT_DIR = os.path.join(RESOURCE_DIR, 'deployment')
APP_DIR = os.path.join(RESOURCE_DIR, 'src')
TEMPLATE_ENV_FILE_NAME = os.path.join(APP_DIR, 'template.env')

###############################################################################
# Input Definitions
###############################################################################

local_input = BoolInput(
    name='local-kebab-app-name',
    description='Use "kebab-app-name" on local machine',
    prompt='Use "kebab-app-name" on local machine?',
    default=True
)

https_input = BoolInput(
    name='kebab-app-name-https',
    description='Whether "kebab-app-name" run on HTTPS',
    prompt='Is "kebab-app-name" run on HTTPS?',
    default=False
)

host_input = StrInput(
    name='kebab-app-name-host',
    description='Hostname of "kebab-app-name"',
    prompt='Hostname of "kebab-app-name"',
    default='localhost'
)
