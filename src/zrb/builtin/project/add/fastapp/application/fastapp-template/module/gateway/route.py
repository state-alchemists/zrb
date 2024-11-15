from ...common.app import app
from ...common.schema import BasicResponse
from ...config import APP_MODE, APP_MODULES
from ...schema.user import NewUserData, UserData
from ..auth.client.factory import client as auth_client

if APP_MODE == "monolith" or "gateway" in APP_MODULES:

    @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def health():
        return BasicResponse(message="ok")

    @app.api_route("/readiness", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def readiness():
        return BasicResponse(message="ok")

    @app.get("/api/v1/users", response_model=list[UserData])
    async def auth_get_all_users():
        return await auth_client.get_all_users()

    @app.post("/api/v1/users", response_model=UserData)
    async def auth_create_user(data: NewUserData):
        return await auth_client.create_user(data)
