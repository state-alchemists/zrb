from fastapp_template.config import APP_COMMUNICATION
from fastapp_template.module.module_template.client.any_client import BaseClient
from fastapp_template.module.module_template.client.api_client import APIClient
from fastapp_template.module.module_template.client.direct_client import DirectClient

if APP_COMMUNICATION == "direct":
    client: BaseClient = DirectClient()
elif APP_COMMUNICATION == "api":
    client: BaseClient = APIClient()
