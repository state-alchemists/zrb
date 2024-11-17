from ....config import APP_COMMUNICATION
from .api_client import APIClient
from .base_client import BaseClient
from .direct_client import DirectClient

if APP_COMMUNICATION == "direct":
    client: BaseClient = DirectClient()
elif APP_COMMUNICATION == "api":
    client: BaseClient = APIClient()
