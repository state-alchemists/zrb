from my_app_name.schema.user import AuthUserResponse
from pydantic import BaseModel


class Page(BaseModel):
    name: str
    caption: str
    url: str
    permission: str | None = None


class AccessiblePage(BaseModel):
    name: str
    caption: str
    url: str
    active: bool


class PageGroup(BaseModel):
    name: str
    caption: str
    pages: list[Page] = []

    def append_page(self, submenu: Page) -> Page:
        self.pages.append(submenu)
        return submenu

    def get_accessible_pages(
        self, submenu_name: str | None = None, user: AuthUserResponse | None = None
    ) -> list[AccessiblePage]:
        return [
            AccessiblePage(
                name=page.name,
                caption=page.caption,
                url=page.url,
                active=page.name == submenu_name,
            )
            for page in self.pages
            if _has_permission(user, page.permission)
        ]


class AccessiblePageGroup(BaseModel):
    name: str
    caption: str
    pages: list[AccessiblePage]
    active: bool


class Navigation(BaseModel):
    items: list[PageGroup | Page] = []

    def append_page_group(self, page_group: PageGroup) -> PageGroup:
        self.items.append(page_group)
        return page_group

    def append_page(self, page: Page) -> Page:
        self.items.append(page)
        return page

    def get_accessible_items(
        self, page_name: str | None, user: AuthUserResponse | None
    ) -> list[AccessiblePageGroup | AccessiblePage]:
        accessible_items = []
        for item in self.items:
            if isinstance(item, Page) and _has_permission(user, item.permission):
                accessible_items.append(
                    AccessiblePage(
                        name=item.name,
                        caption=item.caption,
                        url=item.url,
                        active=item.name == page_name,
                    )
                )
                continue
            accessible_submenus = item.get_accessible_pages(page_name, user)
            if accessible_submenus:
                active = any(submenu.active for submenu in accessible_submenus)
                accessible_items.append(
                    AccessiblePageGroup(
                        name=item.name,
                        caption=item.caption,
                        pages=accessible_submenus,
                        active=active,
                    )
                )
        return accessible_items


def _has_permission(user: AuthUserResponse | None, permission: str | None):
    if permission is None:
        return True
    if user is not None:
        return user.has_permission(permission)
    return False
