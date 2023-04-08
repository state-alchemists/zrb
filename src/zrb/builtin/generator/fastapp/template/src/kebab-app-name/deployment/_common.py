from typing import Mapping
from dotenv import dotenv_values
import os

CURRENT_DIR: str = os.path.dirname(__file__)
APP_DIR: str = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'src'))
TEMPLATE_ENV_FILE_NAME: str = os.path.join(APP_DIR, 'template.env')
TEMPLATE_ENV_MAP: Mapping[str, str] = dotenv_values(TEMPLATE_ENV_FILE_NAME)
