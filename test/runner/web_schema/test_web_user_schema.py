"""Tests for runner/web_schema/user.py User model."""

from unittest.mock import MagicMock

import pytest

from zrb.group.any_group import AnyGroup
from zrb.runner.web_schema.user import User
from zrb.task.any_task import AnyTask


class TestUserModel:
    """Test User Pydantic model."""

    def test_default_user(self):
        """Test default user creation."""
        user = User(username="alice", password="secret")
        assert user.username == "alice"
        assert user.password == "secret"
        assert user.is_super_admin is False
        assert user.is_guest is False
        assert user.accessible_tasks == []

    def test_password_match(self):
        """Test is_password_match method."""
        user = User(username="alice", password="correct")
        assert user.is_password_match("correct") is True
        assert user.is_password_match("wrong") is False


class TestUserCanAccessTask:
    """Test User.can_access_task method."""

    def test_super_admin_can_access_any_task(self):
        """Super admin can access any task."""
        task = MagicMock(spec=AnyTask)
        task.name = "some_task"
        user = User(username="admin", is_super_admin=True)
        assert user.can_access_task(task) is True

    def test_user_can_access_task_by_name(self):
        """User can access task by name if in accessible_tasks."""
        task = MagicMock(spec=AnyTask)
        task.name = "allowed_task"
        user = User(username="alice", accessible_tasks=["allowed_task"])
        assert user.can_access_task(task) is True

    def test_user_can_access_task_by_reference(self):
        """User can access task if task object is in accessible_tasks."""
        task = MagicMock(spec=AnyTask)
        task.name = "some_task"
        user = User(username="alice", accessible_tasks=[task])
        assert user.can_access_task(task) is True

    def test_user_cannot_access_task_not_in_list(self):
        """User cannot access task if not in accessible_tasks."""
        task = MagicMock(spec=AnyTask)
        task.name = "forbidden_task"
        user = User(username="alice", accessible_tasks=["other_task"])
        assert user.can_access_task(task) is False


class TestUserCanAccessGroup:
    """Test User.can_access_group method."""

    def test_super_admin_can_access_any_group(self):
        """Super admin can access any group."""
        group = MagicMock(spec=AnyGroup)
        group.subtasks = {}
        group.subgroups = {}
        user = User(username="admin", is_super_admin=True)
        assert user.can_access_group(group) is True

    def test_user_can_access_group_with_accessible_task(self):
        """User can access group if they can access a task in it."""
        task = MagicMock(spec=AnyTask)
        task.name = "accessible_task"
        task.cli_only = False

        group = MagicMock(spec=AnyGroup)
        group.subtasks = {"accessible_task": task}
        group.subgroups = {}

        user = User(username="alice", accessible_tasks=["accessible_task"])
        assert user.can_access_group(group) is True

    def test_user_cannot_access_group_without_accessible_task(self):
        """User cannot access group if they can't access any task in it."""
        task = MagicMock(spec=AnyTask)
        task.name = "forbidden_task"
        task.cli_only = False

        group = MagicMock(spec=AnyGroup)
        group.subtasks = {"forbidden_task": task}
        group.subgroups = {}

        user = User(username="alice", accessible_tasks=["other_task"])
        assert user.can_access_group(group) is False
