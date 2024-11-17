from ...common.app_factory import app
from ...common.schema import BasicResponse
from ...config import APP_MODE, APP_MODULES
from ...schema.user import NewUserData, UserData
from ..auth.client.factory import client as auth_client

if APP_MODE == "monolith" or "gateway" in APP_MODULES:

    if APP_MODE == "monolith" or (len(APP_MODULES) > 0 and APP_MODULES[0] == "gateway"):

        @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
        async def health():
            return BasicResponse(message="ok")

        @app.api_route(
            "/readiness", methods=["GET", "HEAD"], response_model=BasicResponse
        )
        async def readiness():
            return BasicResponse(message="ok")

    @app.get("/api/v1/users", response_model=list[UserData])
    async def auth_get_all_users():
        return await auth_client.get_all_users()

    @app.post("/api/v1/users", response_model=NewUserData | list[NewUserData])
    async def auth_create_user(data: UserData | list[UserData]):
        return await auth_client.create_user(data)
