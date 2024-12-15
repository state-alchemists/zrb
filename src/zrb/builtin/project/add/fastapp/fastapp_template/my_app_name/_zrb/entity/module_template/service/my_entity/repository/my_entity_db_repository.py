from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.common.error import NotFoundError
from my_app_name.module.my_module.service.my_entity.repository.my_entity_repository import (
    MyEntityRepository,
)
from my_app_name.schema.my_entity import (
    MyEntity,
    MyEntityCreateWithAudit,
    MyEntityResponse,
    MyEntityUpdateWithAudit,
)
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


class MyEntityDBRepository(
    BaseDBRepository[
        MyEntity,
        MyEntityResponse,
        MyEntityCreateWithAudit,
        MyEntityUpdateWithAudit,
    ],
    MyEntityRepository,
):
    db_model = MyEntity
    response_model = MyEntityResponse
    create_model = MyEntityCreateWithAudit
    update_model = MyEntityUpdateWithAudit
    entity_name = "my_entity"
    column_preprocessors = {}
