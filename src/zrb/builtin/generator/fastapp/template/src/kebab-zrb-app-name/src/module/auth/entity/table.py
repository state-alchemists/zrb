from module.auth.integration import Base
from sqlalchemy import Column, ForeignKey, String, Table

user_group = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id")),
    Column("group_id", String, ForeignKey("groups.id")),
)

user_permission = Table(
    "user_permissions",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id")),
    Column("permission_id", String, ForeignKey("permissions.id")),
)

group_permission = Table(
    "group_permissions",
    Base.metadata,
    Column("group_id", String, ForeignKey("groups.id")),
    Column("permission_id", String, ForeignKey("permissions.id")),
)
