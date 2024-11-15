from pydantic import BaseModel


class UpdateUserData(BaseModel):
    username: str


class NewUserData(UpdateUserData):
    password: str


class UserData(UpdateUserData):
    id: str
