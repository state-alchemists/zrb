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


class Nav(BaseModel):
    menus: list[Menu] = []


