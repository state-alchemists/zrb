"""Add user table

Revision ID: 3093c7336477
Revises:
Create Date: 2024-11-20 05:57:01.684118

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3093c7336477"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "permissions",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permission_name"), "permissions", ["name"], unique=True)
    op.create_index(
        op.f("ix_permission_created_at"), "permissions", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_permission_created_by"), "permissions", ["created_by"], unique=False
    )
    op.create_index(
        op.f("ix_permission_updated_at"), "permissions", ["updated_at"], unique=False
    )
    op.create_index(
        op.f("ix_permission_updated_by"), "permissions", ["updated_by"], unique=False
    )

    op.create_table(
        "roles",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_role_name"), "roles", ["name"], unique=True)
    op.create_index(op.f("ix_role_created_at"), "roles", ["created_at"], unique=False)
    op.create_index(op.f("ix_role_created_by"), "roles", ["created_by"], unique=False)
    op.create_index(op.f("ix_role_updated_at"), "roles", ["updated_at"], unique=False)
    op.create_index(op.f("ix_role_updated_by"), "roles", ["updated_by"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("permission_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_role_permissions_permission_id"),
        "role_permissions",
        ["permission_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_permissions_role_id"),
        "role_permissions",
        ["role_id"],
        unique=False,
    )

    op.create_table(
        "users",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_user_active"), "users", ["active"], unique=False)
    op.create_index(op.f("ix_user_created_at"), "users", ["created_at"], unique=False)
    op.create_index(op.f("ix_user_created_by"), "users", ["created_by"], unique=False)
    op.create_index(op.f("ix_user_updated_at"), "users", ["updated_at"], unique=False)
    op.create_index(op.f("ix_user_updated_by"), "users", ["updated_by"], unique=False)

    op.create_table(
        "user_roles",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("access_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("refresh_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("access_token_expired_at", sa.DateTime(), nullable=False),
        sa.Column("refresh_token_expired_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_session_user_id"), "user_sessions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_session_token"), "user_sessions", ["access_token"], unique=True
    )
    op.create_index(
        op.f("ix_user_session_refresh_token"),
        "user_sessions",
        ["refresh_token"],
        unique=True,
    )
    op.create_index(
        op.f("ix_user_session_access_token_expired_at"),
        "user_sessions",
        ["access_token_expired_at"],
    )
    op.create_index(
        op.f("ix_user_session_refresh_token_expired_at"),
        "user_sessions",
        ["refresh_token_expired_at"],
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_user_session_user_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_session_access_token"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_session_refresh_token"), table_name="user_sessions")
    op.drop_index(
        op.f("ix_user_session_access_token_expired_at"), table_name="user_sessions"
    )
    op.drop_index(
        op.f("ix_user_session_refresh_token_expired_at"), table_name="user_sessions"
    )
    op.drop_table("user_sessions")

    op.drop_index(op.f("ix_user_roles_user_id"), table_name="user_roles")
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles")
    op.drop_table("user_roles")

    op.drop_index(op.f("ix_user_username"), table_name="users")
    op.drop_index(op.f("ix_user_active"), table_name="users")
    op.drop_index(op.f("ix_user_updated_by"), table_name="users")
    op.drop_index(op.f("ix_user_updated_at"), table_name="users")
    op.drop_index(op.f("ix_user_created_by"), table_name="users")
    op.drop_index(op.f("ix_user_created_at"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_role_permissions_role_id"), table_name="role_permissions")
    op.drop_index(
        op.f("ix_role_permissions_permission_id"), table_name="role_permissions"
    )
    op.drop_table("role_permissions")

    op.drop_index(op.f("ix_role_name"), table_name="roles")
    op.drop_index(op.f("ix_role_updated_by"), table_name="roles")
    op.drop_index(op.f("ix_role_updated_at"), table_name="roles")
    op.drop_index(op.f("ix_role_created_by"), table_name="roles")
    op.drop_index(op.f("ix_role_created_at"), table_name="roles")
    op.drop_table("roles")

    op.drop_index(op.f("ix_permission_updated_by"), table_name="permissions")
    op.drop_index(op.f("ix_permission_updated_at"), table_name="permissions")
    op.drop_index(op.f("ix_permission_created_by"), table_name="permissions")
    op.drop_index(op.f("ix_permission_created_at"), table_name="permissions")
    op.drop_index(op.f("ix_permission_name"), table_name="permissions")
    op.drop_table("permissions")
    # ### end Alembic commands ###
