import asyncio

from config import app_max_not_ready
from integration.log import logger


class AppState:
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        self.readiness: bool = False
        self.liveness: bool = False

    def set_liveness(self, value: bool):
        self.liveness = value

    def set_readiness(self, value: bool):
        self.readiness = value

    def get_liveness(self) -> bool:
        return self.liveness

    def get_readiness(self) -> bool:
        return self.readiness


app_state = AppState()


async def set_not_ready_on_error(exception: Exception):
    logger.critical(exception)
    app_state.set_readiness(False)
    await asyncio.sleep(app_max_not_ready)
    app_state.set_liveness(False)
