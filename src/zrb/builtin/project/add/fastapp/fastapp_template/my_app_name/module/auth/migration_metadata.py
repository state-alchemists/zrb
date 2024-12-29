from my_app_name.schema.permission import Permission
from my_app_name.schema.role import Role, RolePermission
from my_app_name.schema.session import Session
from my_app_name.schema.user import User, UserRole
from sqlalchemy import MetaData

metadata = MetaData()

Permission.metadata = metadata
Permission.__table__.tometadata(metadata)

Role.metadata = metadata
Role.__table__.tometadata(metadata)
RolePermission.metadata = metadata
RolePermission.__table__.tometadata(metadata)

User.metadata = metadata
User.__table__.tometadata(metadata)
UserRole.metadata = metadata
UserRole.__table__.tometadata(metadata)

Session.metadata = metadata
Session.__table__.tometadata(metadata)
