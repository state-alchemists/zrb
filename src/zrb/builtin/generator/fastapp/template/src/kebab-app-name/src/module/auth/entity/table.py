from sqlalchemy import Column, Integer, Table, ForeignKey
from module.auth.component.base import Base

user_group = Table(
    'user_groups',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('group_id', Integer, ForeignKey('groups.id')),
)

user_permission = Table(
    'user_permissions',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('permission_id', Integer, ForeignKey('permissions.id')),
)

group_permission = Table(
    'group_permissions',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('groups.id')),
    Column('permission_id', Integer, ForeignKey('permissions.id')),
)
