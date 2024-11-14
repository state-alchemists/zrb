from pydantic import BaseModel


class UserData(BaseModel):
    username: str


class NewUserData(UserData):
    password: str


class User(UserData):
    id: str
