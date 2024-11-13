from config import APP_COMMUNICATION, APP_LIBRARY_BASE_URL
from module.library.client.api_client import ApiClient
from module.library.client.base_client import BaseClient
from module.library.client.direct_client import DirectClient
from module.library.usecase import usecase

if APP_COMMUNICATION == "direct":
    client: BaseClient = DirectClient(usecase=usecase)
elif APP_COMMUNICATION == "api":
    client: BaseClient = ApiClient(base_url=APP_LIBRARY_BASE_URL)
