from component.repo import DBEntityMixin, DBRepo, Repo
from module.log.integration import Base
from module.log.schema.activity import Activity, ActivityData
from sqlalchemy import Column, String, Text


class DBEntityActivity(Base, DBEntityMixin):
    class Config:
        from_attributes = True

    __tablename__ = "activities"
    action = Column(String)
    entity: Column = Column(String)
    data: Column = Column(Text)


class ActivityRepo(Repo[Activity, ActivityData]):
    pass


class ActivityDBRepo(DBRepo[Activity, ActivityData], ActivityRepo):
    schema_cls = Activity
    db_entity_cls = DBEntityActivity
