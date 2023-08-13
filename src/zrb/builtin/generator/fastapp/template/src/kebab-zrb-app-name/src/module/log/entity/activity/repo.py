from sqlalchemy import Column, String, Text
from core.repo import Repo, DBEntityMixin, DBRepo
from module.log.schema.activity import (
    Activity, ActivityData
)
from module.log.component import Base


class DBEntityActivity(Base, DBEntityMixin):
    __tablename__ = "activities"
    action = Column(String)
    entity: Column = Column(String)
    data: Column = Column(Text)


class ActivityRepo(Repo[Activity, ActivityData]):
    pass


class ActivityDBRepo(
    DBRepo[Activity, ActivityData], ActivityRepo
):
    schema_cls = Activity
    db_entity_cls = DBEntityActivity
