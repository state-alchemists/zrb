from typing import Callable

from zrb.runner.web_schema.user import User
from zrb.task.any_task import AnyTask


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
        self.secret_key = secret_key
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_minutes = refresh_token_expire_minutes
        self.access_token_cookie_name = access_token_cookie_name
        self.refresh_token_cookie_name = refresh_token_cookie_name
        self.enable_auth = enable_auth
        self.port = port
        self._user_list = []
        self.super_admin_username = super_admin_username
        self.super_admin_password = super_admin_password
        self.guest_username = guest_username
        self.guest_accessible_tasks = guest_accessible_tasks
        self._find_user_by_username = find_user_by_username

    @property
    def default_user(self) -> User:
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
    def super_admin(self) -> User:
        return User(
            username=self.super_admin_username,
            password=self.super_admin_password,
            is_super_admin=True,
        )

    @property
    def user_list(self) -> list[User]:
        if not self.enable_auth:
            return [self.default_user]
        return self._user_list + [self.super_admin, self.default_user]

    def set_guest_accessible_tasks(self, tasks: list[AnyTask | str]):
        self.guest_accessible_tasks = tasks

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

    def find_user_by_username(self, username: str) -> User | None:
        user = None
        if self._find_user_by_username is not None:
            user = self._find_user_by_username(username)
        if user is None:
            user = next((u for u in self.user_list if u.username == username), None)
        return user
