from ...common.app import app
from ...config import APP_MODE, APP_MODULES
from .usecase import usecase

if APP_MODE == "microservices" and "library" in APP_MODULES:

    @app.get("/library/greeting")
    def greet(name: str) -> str:
        return usecase.greet(name)
