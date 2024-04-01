from module.log.integration.base import Base
from sqlalchemy import Column, ForeignKey, Integer, Table

"""
You should put any "many-to-many" table declarations in this file.
For example:
```
# Many-to-many table to relate users and permissions
user_permission = Table(
    "user_permission",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("permission_id", Integer, ForeignKey("permissions.id")),
)
```

Remove the following assertions:
"""
assert Column
assert Integer
assert Table
assert ForeignKey
assert Base
