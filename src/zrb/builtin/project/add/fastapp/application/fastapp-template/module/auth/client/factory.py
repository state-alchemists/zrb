from ....config import APP_COMMUNICATION, APP_LIBRARY_BASE_URL
from ..service.user.usecase import user_usecase
from .base_client import BaseClient

if APP_COMMUNICATION == "direct":
    client: BaseClient = user_usecase.as_direct_client()
elif APP_COMMUNICATION == "api":
    client: BaseClient = user_usecase.as_api_client(base_url=APP_LIBRARY_BASE_URL)
