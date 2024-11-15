from uuid import uuid4

from sqlalchemy import String, delete, update
from sqlalchemy.future import select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from ......schema.user import NewUserData, UpdateUserData, UserData
from .repository import UserRepository


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
    password: Mapped[str] = mapped_column(String(50))


def create_user_model(new_user_data: NewUserData) -> UserModel:
    return UserModel(
        id=str(uuid4()),
        username=new_user_data.username,
        password=new_user_data.password,
    )


def get_user_data(user_model: UserModel) -> UserData:
    return UserData(
        id=user_model.id,
        username=user_model.username,
    )


class UserDBRepository(UserRepository):
    def __init__(self, session_maker: sessionmaker[Session]):
        self.session_maker = session_maker

    async def create_user(self, new_user_data: NewUserData) -> UserData:
        async with self.session_maker() as session:
            user_model = create_user_model(new_user_data)
            session.add(user_model)
            await session.commit()
            await session.refresh(user_model)
            return get_user_data(user_model)

    async def get_user_by_id(self, user_id: str) -> UserData | None:
        async with self.session_maker() as session:
            result = await session.execute(select(UserModel).filter_by(id=user_id))
            user_model = result.scalar_one_or_none()
            if user_model:
                return get_user_data(user_model)
            return None

    async def get_all_users(self) -> list[UserData]:
        async with self.session_maker() as session:
            result = await session.execute(select(UserModel))
            user_models = result.scalars().all()
            return [get_user_data(user_model) for user_model in user_models]

    async def update_user(
        self, user_id: str, update_user_data: UpdateUserData
    ) -> UserData | None:
        async with self.session_maker() as session:
            stmt = (
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(username=update_user_data.username)
                .execution_options(synchronize_session="fetch")
            )
            await session.execute(stmt)
            await session.commit()
            return await self.get_user_by_id(user_id)

    async def delete_user(self, user_id: str) -> None:
        async with self.session_maker() as session:
            stmt = delete(UserModel).where(UserModel.id == user_id)
            await session.execute(stmt)
            await session.commit()

    async def create_users_bulk(
        self, new_users_data: list[NewUserData]
    ) -> list[UserData]:
        async with self.session_maker() as session:
            user_models = [create_user_model(user_data) for user_data in new_users_data]
            session.add_all(user_models)
            await session.commit()
            return [get_user_data(user_model) for user_model in user_models]

    async def get_user_by_username(self, username: str) -> UserData | None:
        async with self.session_maker() as session:
            result = await session.execute(
                select(UserModel).filter_by(username=username)
            )
            user_model = result.scalar_one_or_none()
            if user_model:
                return get_user_data(user_model)
            return None
