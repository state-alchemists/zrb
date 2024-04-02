from component.repo import DBEntityMixin, DBRepo, Repo
from module.snake_zrb_module_name.integration import Base
from module.snake_zrb_module_name.schema.snake_zrb_entity_name import (
    PascalZrbEntityName,
    PascalZrbEntityNameData,
)
from sqlalchemy import Column, String


class DBEntityPascalZrbEntityName(Base, DBEntityMixin):
    class Config:
        from_attributes = True

    __tablename__ = "snake_zrb_plural_entity_name"
    snake_zrb_column_name = Column(String)


class PascalZrbEntityNameRepo(Repo[PascalZrbEntityName, PascalZrbEntityNameData]):
    pass


class PascalZrbEntityNameDBRepo(
    DBRepo[PascalZrbEntityName, PascalZrbEntityNameData], PascalZrbEntityNameRepo
):
    schema_cls = PascalZrbEntityName
    db_entity_cls = DBEntityPascalZrbEntityName
