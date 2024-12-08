from fastapp_template.schema.user import User
from sqlalchemy import MetaData

metadata = MetaData()
User.metadata = metadata
User.__table__.tometadata(metadata)
