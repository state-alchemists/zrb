from fastapp_template.common.base_db_repository import BaseDBRepository
from fastapp_template.common.error import NotFoundError
from fastapp_template.module.my_module.service.my_entity.repository.my_entity_repository import (
    MyEntityRepository,
)
from fastapp_template.schema.my_entity import (
    MyEntity,
    MyEntityCreate,
    MyEntityResponse,
    MyEntityUpdate,
)
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


class MyEntityDBRepository(
    BaseDBRepository[MyEntity, MyEntityResponse, MyEntityCreate, MyEntityUpdate],
    MyEntityRepository,
):
    db_model = MyEntity
    response_model = MyEntityResponse
    create_model = MyEntityCreate
    update_model = MyEntityUpdate
    entity_name = "my_entity"
    column_preprocessors = {}
