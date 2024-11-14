from ....schema.user import NewUserData, User, UserData


class Usecase:
    def get_user_by_id(id: str) -> UserData:
        pass

    def get_user() -> list[UserData]:
        pass

    def insert_user(data: NewUserData) -> User:
        pass

    def insert_users(data: list[NewUserData]) -> list[User]:
        pass

    def update_user(id: str, data: NewUserData) -> User:
        pass


user_usecase = Usecase()
