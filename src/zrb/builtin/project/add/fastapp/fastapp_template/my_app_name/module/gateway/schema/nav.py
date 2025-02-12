from my_app_name.schema.user import AuthUserResponse
from pydantic import BaseModel


class Submenu(BaseModel):
    name: str
    caption: str
    url: str
    permission: str


class Menu(BaseModel):
    name: str
    caption: str
    children: list[Submenu] = []

    def get_permitted_children(self, user: AuthUserResponse | None) -> list[Submenu]:
        if user is None:
            return []
        return [
            child for child in self.children if user.has_permission(child.permission)
        ]


class Nav(BaseModel):
    menus: list[Menu] = []
