from fastapp_template.config import APP_COMMUNICATION
from fastapp_template.module.auth.client.any_client import AnyClient
from fastapp_template.module.auth.client.api_client import APIClient
from fastapp_template.module.auth.client.direct_client import DirectClient

if APP_COMMUNICATION == "direct":
    client: AnyClient = DirectClient()
elif APP_COMMUNICATION == "api":
    client: AnyClient = APIClient()
