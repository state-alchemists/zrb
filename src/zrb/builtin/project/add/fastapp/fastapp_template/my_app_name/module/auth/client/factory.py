from my_app_name.config import APP_COMMUNICATION
from my_app_name.module.auth.client.any_client import AnyClient
from my_app_name.module.auth.client.api_client import APIClient
from my_app_name.module.auth.client.direct_client import DirectClient

if APP_COMMUNICATION == "direct":
    client: AnyClient = DirectClient()
elif APP_COMMUNICATION == "api":
    client: AnyClient = APIClient()
