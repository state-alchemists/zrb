from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.common.error import NotFoundError
from my_app_name.module.auth.service.user.repository.user_repository import (
    UserRepository,
)
from my_app_name.schema.user import (
    User,
    UserCreateWithAudit,
    UserResponse,
    UserUpdateWithAudit,
)
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


class UserDBRepository(
    BaseDBRepository[User, UserResponse, UserCreateWithAudit, UserUpdateWithAudit],
    UserRepository,
):
    db_model = User
    response_model = UserResponse
    create_model = UserCreateWithAudit
    update_model = UserUpdateWithAudit
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
