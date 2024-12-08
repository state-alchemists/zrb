from fastapp_template.common.base_db_repository import BaseDBRepository
from fastapp_template.common.error import NotFoundError
from fastapp_template.module.auth.service.user.repository.user_repository import (
    UserRepository,
)
from fastapp_template.schema.user import User, UserCreate, UserResponse, UserUpdate
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


class UserDBRepository(
    BaseDBRepository[User, UserResponse, UserCreate, UserUpdate], UserRepository
):
    db_model = User
    response_model = UserResponse
    create_model = UserCreate
    update_model = UserUpdate
    entity_name = "user"
    column_preprocessors = {"password": hash_password}

    async def get_by_credentials(self, username: str, password: str) -> UserResponse:
        statement = select(User).where(User.username == username)
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                user = await session.exec(statement).first
        else:
            with Session(self.engine) as session:
                user = session.exec(statement).first()
        if not user or not pwd_context.verify(password, user.hashed_password):
            raise NotFoundError(f"{self.entity_name} not found")
        return self._to_response(user)
