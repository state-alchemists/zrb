from sqlalchemy import Column, String, Table, ForeignKey
from module.auth.component import Base

user_group = Table(
    'user_groups',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id')),
    Column('group_id', String, ForeignKey('groups.id')),
)

user_permission = Table(
    'user_permissions',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id')),
    Column('permission_id', String, ForeignKey('permissions.id')),
)

group_permission = Table(
    'group_permissions',
    Base.metadata,
    Column('group_id', String, ForeignKey('groups.id')),
    Column('permission_id', String, ForeignKey('permissions.id')),
)
