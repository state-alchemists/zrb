from fastapp.config import APP_COMMUNICATION
from fastapp.module.auth.client.api_client import APIClient
from fastapp.module.auth.client.base_client import BaseClient
from fastapp.module.auth.client.direct_client import DirectClient

if APP_COMMUNICATION == "direct":
    client: BaseClient = DirectClient()
elif APP_COMMUNICATION == "api":
    client: BaseClient = APIClient()
