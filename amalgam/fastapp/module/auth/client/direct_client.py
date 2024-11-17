from ..service.user.usecase import user_usecase
from .base_client import BaseClient


class DirectClient(BaseClient, user_usecase.as_direct_client()):
    pass
