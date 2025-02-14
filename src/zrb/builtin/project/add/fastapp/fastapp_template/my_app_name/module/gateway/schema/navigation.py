from my_app_name.schema.user import AuthUserResponse
from pydantic import BaseModel


class Submenu(BaseModel):
    name: str
    caption: str
    url: str
    permission: str


class AccessibleSubmenu(BaseModel):
    name: str
    caption: str
    url: str
    active: bool


class Menu(BaseModel):
    name: str
    caption: str
    submenus: list[Submenu] = []

    def append_submenu(self, submenu: Submenu) -> Submenu:
        self.submenus.append(submenu)
        return submenu

    def get_accessible_submenus(
        self, submenu_name: str | None = None, user: AuthUserResponse | None = None
    ) -> list[AccessibleSubmenu]:
        if user is None:
            return []
        return [
            AccessibleSubmenu(
                name=Submenu.name,
                caption=Submenu.caption,
                url=Submenu.url,
                active=Submenu.name == submenu_name,
            )
            for submenu in self.submenus
            if user.has_permission(submenu.permission)
        ]


class AccessibleMenu(BaseModel):
    name: str
    caption: str
    submenus: list[AccessibleSubmenu]
    active: bool


class Navigation(BaseModel):
    menus: list[Menu] = []

    def append_menu(self, menu: Menu) -> Menu:
        self.menus.append(menu)
        return menu

    def get_acccessible_menus(
        self, submenu_name: str | None, user: AuthUserResponse | None
    ) -> list[AccessibleMenu]:
        if user is None:
            return []
        accessible_menus = []
        for menu in self.menus:
            accessible_submenus = menu.get_accessible_submenus(submenu_name, user)
            if accessible_submenus:
                active = any(submenu.active for submenu in accessible_submenus)
                accessible_menus.append(
                    AccessibleMenu(
                        name=menu.name,
                        caption=menu.caption,
                        submenus=accessible_submenus,
                        active=active,
                    )
                )
        return accessible_menus
