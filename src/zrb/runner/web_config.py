from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel, ConfigDict

from zrb.config import (
    WEB_ACCESS_TOKEN_COOKIE_NAME,
    WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
    WEB_ENABLE_AUTH,
    WEB_GUEST_USERNAME,
    WEB_HTTP_PORT,
    WEB_REFRESH_TOKEN_COOKIE_NAME,
    WEB_SECRET_KEY,
    WEB_SUPER_ADMIN_PASSWORD,
    WEB_SUPER_ADMIN_USERNAME,
)
from zrb.group.any_group import AnyGroup
from zrb.task.any_task import AnyTask
from zrb.util.group import get_all_subtasks

if TYPE_CHECKING:
    # Import Request only for type checking to reduce runtime dependencies
    from fastapi import Request


class User(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    username: str
    password: str = ""
    is_super_admin: bool = False
    is_guest: bool = False
    accessible_tasks: list[AnyTask | str] = []

    def is_password_match(self, password: str) -> bool:
        return self.password == password

    def can_access_group(self, group: AnyGroup) -> bool:
        if self.is_super_admin:
            return True
        all_tasks = get_all_subtasks(group, web_only=True)
        if any(self.can_access_task(task) for task in all_tasks):
            return True
        return False

    def can_access_task(self, task: AnyTask) -> bool:
        if self.is_super_admin:
            return True
        if task.name in self.accessible_tasks or task in self.accessible_tasks:
            return True
        return False


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class WebConfig:
    def __init__(
        self,
        port: int,
        secret_key: str,
        access_token_expire_minutes: int,
        refresh_token_expire_minutes: int,
        access_token_cookie_name: str,
        refresh_token_cookie_name: str,
        enable_auth: bool,
        super_admin_username: str,
        super_admin_password: str,
        guest_username: str,
        guest_accessible_tasks: list[AnyTask | str] = [],
        find_user_by_username: Callable[[str], User | None] | None = None,
    ):
        self._secret_key = secret_key
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_minutes = refresh_token_expire_minutes
        self._access_token_cookie_name = access_token_cookie_name
        self._refresh_token_cookie_name = refresh_token_cookie_name
        self._enable_auth = enable_auth
        self._port = port
        self._user_list = []
        self._super_admin_username = super_admin_username
        self._super_admin_password = super_admin_password
        self._guest_username = guest_username
        self._guest_accessible_tasks = guest_accessible_tasks
        self._find_user_by_username = find_user_by_username

    @property
    def port(self) -> int:
        return self._port

    @property
    def access_token_cookie_name(self) -> str:
        return self._access_token_cookie_name

    @property
    def refresh_token_cookie_name(self) -> str:
        return self._refresh_token_cookie_name

    @property
    def access_token_max_age(self) -> int:
        self._access_token_expire_minutes * 60

    @property
    def refresh_token_max_age(self) -> int:
        self._refresh_token_expire_minutes * 60

    @property
    def default_user(self) -> User:
        if self._enable_auth:
            return User(
                username=self._guest_username,
                password="",
                is_guest=True,
                accessible_tasks=self._guest_accessible_tasks,
            )
        return User(
            username=self._guest_username,
            password="",
            is_guest=True,
            is_super_admin=True,
        )

    @property
    def super_admin(self) -> User:
        return User(
            username=self._super_admin_username,
            password=self._super_admin_password,
            is_super_admin=True,
        )

    @property
    def user_list(self) -> list[User]:
        if not self._enable_auth:
            return [self.default_user]
        return self._user_list + [self.super_admin, self.default_user]

    def set_find_user_by_username(
        self, find_user_by_username: Callable[[str], User | None]
    ):
        self._find_user_by_username = find_user_by_username

    def append_user(self, user: User):
        duplicates = [
            existing_user
            for existing_user in self.user_list
            if existing_user.username == user.username
        ]
        if len(duplicates) > 0:
            raise ValueError(f"User already exists {user.username}")
        self._user_list.append(user)

    def enable_auth(self):
        self._enable_auth = True

    def disable_auth(self):
        self._enable_auth = False

    def find_user_by_username(self, username: str) -> User | None:
        user = None
        if self._find_user_by_username is not None:
            user = self._find_user_by_username(username)
        if user is None:
            user = next((u for u in self.user_list if u.username == username), None)
        return user

    def get_user_by_request(self, request: "Request") -> User | None:
        from fastapi.security import OAuth2PasswordBearer

        if not self._enable_auth:
            return self.default_user
        # Normally we use "Depends"
        oauth2_password_bearer = OAuth2PasswordBearer(
            tokenUrl="/api/v1/login", auto_error=False
        )
        bearer_token = oauth2_password_bearer(request)
        token_user = self._get_user_from_token(bearer_token)
        if token_user is not None:
            return token_user
        cookie_user = self._get_user_from_cookie(request)
        if cookie_user is not None:
            return cookie_user
        return self.default_user

    def _get_user_from_token(self, token: str) -> User | None:
        try:
            from jose import jwt

            payload = jwt.decode(token, self._secret_key)
            username: str = payload.get("sub")
            if username is None:
                return None
            user = self.find_user_by_username(username)
            if user is None:
                return None
            return user
        except Exception:
            return None

    def _get_user_from_cookie(self, request: "Request") -> User | None:
        token = request.cookies.get(self._access_token_cookie_name)
        if token:
            return self._get_user_from_token(token)
        return None

    def get_user_by_credentials(self, username: str, password: str) -> User:
        user = self.find_user_by_username(username)
        if user is None or not user.is_password_match(password):
            return self.default_user
        return user

    def generate_tokens(self, username: str, password: str) -> Token:
        if not self._enable_auth:
            user = self.default_user
        else:
            user = self.get_user_by_credentials(username, password)
        access_token = self.create_access_token(user.username)
        refresh_token = self.create_refresh_token(user.username)
        return Token(
            access_token=access_token, refresh_token=refresh_token, token_type="bearer"
        )

    def create_access_token(self, username: str) -> str:
        from jose import jwt

        expire = datetime.now() + timedelta(minutes=self._access_token_expire_minutes)
        to_encode = {"sub": username, "exp": expire, "type": "access"}
        return jwt.encode(to_encode, self._secret_key)

    def create_refresh_token(self, username: str) -> str:
        from jose import jwt

        expire = datetime.now() + timedelta(minutes=self._refresh_token_expire_minutes)
        to_encode = {"sub": username, "exp": expire, "type": "refresh"}
        return jwt.encode(to_encode, self._secret_key)

    def refresh_tokens(self, refresh_token: str) -> Token:
        from fastapi import HTTPException
        from jose import jwt

        try:
            payload = jwt.decode(refresh_token, self._secret_key)
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Invalid token type")
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(status_code=401, detail="Invalid refresh token")
            user = self.find_user_by_username(username)
            if user is None:
                raise HTTPException(status_code=401, detail="User not found")

            new_access_token = self.create_access_token(username)
            new_refresh_token = self.create_refresh_token(username)
            return Token(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
            )
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid refresh token")


web_config = WebConfig(
    port=WEB_HTTP_PORT,
    secret_key=WEB_SECRET_KEY,
    access_token_expire_minutes=WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    refresh_token_expire_minutes=WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
    access_token_cookie_name=WEB_ACCESS_TOKEN_COOKIE_NAME,
    refresh_token_cookie_name=WEB_REFRESH_TOKEN_COOKIE_NAME,
    enable_auth=WEB_ENABLE_AUTH,
    super_admin_username=WEB_SUPER_ADMIN_USERNAME,
    super_admin_password=WEB_SUPER_ADMIN_PASSWORD,
    guest_username=WEB_GUEST_USERNAME,
)
