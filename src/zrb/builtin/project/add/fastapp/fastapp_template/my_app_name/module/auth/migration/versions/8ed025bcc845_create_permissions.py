"""create_permissions

Revision ID: 8ed025bcc845
Revises: 3093c7336477
Create Date: 2025-02-08 19:09:14.536559

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel  # 🔥 FastApp Modification
from alembic import op
from module.auth.migration_metadata import metadata

# revision identifiers, used by Alembic.
revision: str = "8ed025bcc845"
down_revision: Union[str, None] = "3093c7336477"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.bulk_insert(
        metadata.tables["permissions"],
        [
            # permission
            {"name": "permission:create", "description": "create permission"},
            {"name": "permission:read", "description": "read permission"},
            {"name": "permission:update", "description": "update permission"},
            {"name": "permission:delete", "description": "delete permission"},
            # role
            {"name": "role:create", "description": "create role"},
            {"name": "role:read", "description": "read role"},
            {"name": "role:update", "description": "update role"},
            {"name": "role:delete", "description": "delete role"},
            # user
            {"name": "user:create", "description": "create user"},
            {"name": "user:read", "description": "read user"},
            {"name": "user:update", "description": "update user"},
            {"name": "user:delete", "description": "delete user"},
        ],
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.execute(
        sa.delete(metadata.tables["permissions"]).where(
            metadata.tables["permissions"].c.name.in_(
                # user
                "user:create",
                "user:read",
                "user:update",
                "user:delete",
                # role
                "role:create",
                "role:read",
                "role:update",
                "role:delete",
                # permission
                "permission:create",
                "permission:read",
                "permission:update",
                "permission:delete",
            )
        )
    )
    # ### end Alembic commands ###
