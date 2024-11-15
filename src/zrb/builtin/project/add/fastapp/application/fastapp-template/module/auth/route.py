from ...common.app import app
from ...common.schema import BasicResponse
from ...config import APP_MODE, APP_MODULES
from ...schema.user import NewUserData, UserData
from .service.user.usecase import user_usecase

if APP_MODE == "microservices" and "auth" in APP_MODULES:

    @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def health():
        return BasicResponse(message="ok")

    @app.api_route("/readiness", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def readiness():
        return BasicResponse(message="ok")

    @app.post("/api/v1/users", response_model=UserData)
    async def create_user(data: NewUserData) -> UserData:
        return await user_usecase.create_user(data)

    @app.get("/api/v1/users", response_model=list[UserData])
    async def get_all_users() -> list[UserData]:
        return await user_usecase.get_all_users()
