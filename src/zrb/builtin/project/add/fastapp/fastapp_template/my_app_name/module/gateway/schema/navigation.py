from my_app_name.schema.user import AuthUserResponse
from pydantic import BaseModel


class Submenu(BaseModel):
    name: str
    caption: str
    url: str
    permission: str


class AccessibleSubmenu(Submenu):
    active: bool


class Menu(BaseModel):
    name: str
    caption: str
    submenus: list[Submenu] = []

    def get_accessible_submenus(
        self,
        submenu_name: str | None = None,
        user: AuthUserResponse | None = None
    ) -> list[Submenu]:
        if user is None:
            return []
        return [
            AccessibleSubmenu(
                **
            )
            for submenu in self.submenus
            if user.has_permission(submenu.permission)
        ]


class Navigation(BaseModel):
    menus: list[Menu] = []

    def get_acccessible_menus(
        self, user: AuthUserResponse | None
    ) -> list[Menu]:
        if user is None:
            return []
        return [
            menu
            for menu in self.menus
            if len(menu.get_accessible_submenus(user)) > 0
        ]
