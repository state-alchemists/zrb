from sqlalchemy import Column, String
from core.repo import Repo, DBEntityMixin, DBRepo
from module.snake_module_name.schema.snake_entity_name import (
    PascalEntityName, PascalEntityNameData
)
from module.snake_module_name.component import Base


class DBEntityPascalEntityName(Base, DBEntityMixin):
    __tablename__ = "snake_plural_entity_name"
    snake_column_name = Column(String)


class PascalEntityNameRepo(Repo[PascalEntityName, PascalEntityNameData]):
    pass


class PascalEntityNameDBRepo(
    DBRepo[PascalEntityName, PascalEntityNameData], PascalEntityNameRepo
):
    schema_cls = PascalEntityName
    db_entity_cls = DBEntityPascalEntityName
