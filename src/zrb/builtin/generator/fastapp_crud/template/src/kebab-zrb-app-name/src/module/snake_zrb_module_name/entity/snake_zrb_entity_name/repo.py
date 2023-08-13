from sqlalchemy import Column, String
from core.repo import Repo, DBEntityMixin, DBRepo
from module.snake_zrb_module_name.schema.snake_zrb_entity_name import (
    PascalZrbEntityName, PascalZrbEntityNameData
)
from module.snake_zrb_module_name.component import Base


class DBEntityPascalZrbEntityName(Base, DBEntityMixin):
    __tablename__ = "snake_zrb_plural_entity_name"
    snake_zrb_column_name = Column(String)


class PascalZrbEntityNameRepo(Repo[PascalZrbEntityName, PascalZrbEntityNameData]):
    pass


class PascalZrbEntityNameDBRepo(
    DBRepo[PascalZrbEntityName, PascalZrbEntityNameData], PascalZrbEntityNameRepo
):
    schema_cls = PascalZrbEntityName
    db_entity_cls = DBEntityPascalZrbEntityName
