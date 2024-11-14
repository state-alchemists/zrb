from ....config import APP_COMMUNICATION, APP_LIBRARY_BASE_URL
from ..usecase import usecase
from .api_client import ApiClient
from .base_client import BaseClient
from .direct_client import DirectClient

if APP_COMMUNICATION == "direct":
    client: BaseClient = DirectClient(usecase=usecase)
elif APP_COMMUNICATION == "api":
    client: BaseClient = ApiClient(base_url=APP_LIBRARY_BASE_URL)