from typing import TYPE_CHECKING, Callable

from zrb.config.config import CFG
from zrb.task.any_task import AnyTask

if TYPE_CHECKING:
    from zrb.runner.web_schema.user import User


class WebAuthConfig:
    def __init__(
        self,
        secret_key: str | None = None,
        access_token_expire_minutes: int | None = None,
        refresh_token_expire_minutes: int | None = None,
        access_token_cookie_name: str | None = None,
        refresh_token_cookie_name: str | None = None,
        enable_auth: bool | None = None,
        super_admin_username: str | None = None,
        super_admin_password: str | None = None,
        guest_username: str | None = None,
        guest_accessible_tasks: list[AnyTask | str] = [],
        find_user_by_username: Callable[[str], "User | None"] | None = None,
    ):
        self._secret_key = secret_key
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_minutes = refresh_token_expire_minutes
        self._access_token_cookie_name = access_token_cookie_name
        self._refresh_token_cookie_name = refresh_token_cookie_name
        self._enable_auth = enable_auth
        self._super_admin_username = super_admin_username
        self._super_admin_password = super_admin_password
        self._guest_username = guest_username
        self._user_list: list["User"] = []
        self._guest_accessible_tasks = guest_accessible_tasks
        self._find_user_by_username = find_user_by_username

    @property
    def secret_key(self) -> str:
        if self._secret_key is not None:
            return self._secret_key
        return CFG.WEB_SECRET_KEY

    @property
    def access_token_expire_minutes(self) -> int:
        if self._access_token_expire_minutes is not None:
            return self._access_token_expire_minutes
        return CFG.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES

    @property
    def refresh_token_expire_minutes(self) -> int:
        if self._refresh_token_expire_minutes is not None:
            return self._refresh_token_expire_minutes
        return CFG.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES

    @property
    def access_token_cookie_name(self) -> str:
        if self._access_token_cookie_name is not None:
            return self._access_token_cookie_name
        return CFG.WEB_ACCESS_TOKEN_COOKIE_NAME

    @property
    def refresh_token_cookie_name(self) -> str:
        if self._refresh_token_cookie_name is not None:
            return self._refresh_token_cookie_name
        return CFG.WEB_REFRESH_TOKEN_COOKIE_NAME

    @property
    def enable_auth(self) -> bool:
        if self._enable_auth is not None:
            return self._enable_auth
        return CFG.WEB_ENABLE_AUTH

    @property
    def super_admin_username(self) -> str:
        if self._super_admin_username is not None:
            return self._super_admin_username
        return CFG.WEB_SUPER_ADMIN_USERNAME

    @property
    def super_admin_password(self) -> str:
        if self._super_admin_password is not None:
            return self._super_admin_password
        return CFG.WEB_SUPER_ADMIN_PASSWORD

    @property
    def guest_username(self) -> str:
        if self._guest_username is not None:
            return self._guest_username
        return CFG.WEB_GUEST_USERNAME

    @property
    def guest_accessible_tasks(self) -> list[AnyTask | str]:
        return self._guest_accessible_tasks

    @property
    def default_user(self) -> "User":
        from zrb.runner.web_schema.user import User

        if self.enable_auth:
            return User(
                username=self.guest_username,
                password="",
                is_guest=True,
                accessible_tasks=self.guest_accessible_tasks,
            )
        return User(
            username=self.guest_username,
            password="",
            is_guest=True,
            is_super_admin=True,
        )

    @property
    def super_admin(self) -> "User":
        from zrb.runner.web_schema.user import User

        return User(
            username=self.super_admin_username,
            password=self.super_admin_password,
            is_super_admin=True,
        )

    @property
    def user_list(self) -> list["User"]:
        if not self.enable_auth:
            return [self.default_user]
        return self._user_list + [self.super_admin, self.default_user]

    def set_secret_key(self, secret_key: str):
        self._secret_key = secret_key

    def set_access_token_expire_minutes(self, minutes: int):
        self._access_token_expire_minutes = minutes

    def set_refresh_token_expire_minutes(self, minutes: int):
        self._refresh_token_expire_minutes = minutes

    def set_access_token_cookie_name(self, name: str):
        self._access_token_cookie_name = name

    def set_refresh_token_cookie_name(self, name: str):
        self._refresh_token_cookie_name = name

    def set_enable_auth(self, enable: bool):
        self._enable_auth = enable

    def set_super_admin_username(self, username: str):
        self._super_admin_username = username

    def set_super_admin_password(self, password: str):
        self._super_admin_password = password

    def set_guest_username(self, username: str):
        self._guest_username = username

    def set_guest_accessible_tasks(self, tasks: list[AnyTask | str]):
        self._guest_accessible_tasks = tasks

    def set_find_user_by_username(
        self, find_user_by_username: Callable[[str], "User | None"]
    ):
        self._find_user_by_username = find_user_by_username

    def append_user(self, user: "User"):
        duplicates = [
            existing_user
            for existing_user in self.user_list
            if existing_user.username == user.username
        ]
        if len(duplicates) > 0:
            raise ValueError(f"User already exists {user.username}")
        self._user_list.append(user)

    def find_user_by_username(self, username: str) -> "User | None":
        user = None
        if self._find_user_by_username is not None:
            user = self._find_user_by_username(username)
        if user is None:
            user = next((u for u in self.user_list if u.username == username), None)
        return user


web_auth_config = WebAuthConfig()
