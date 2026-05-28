"""Tests for runner/web_util/html.py — covers the auth-link variants and
parent_url normalization that previously had no test."""

from unittest.mock import MagicMock

from zrb.runner.web_schema.user import User
from zrb.runner.web_util.html import (
    get_html_auth_link,
    get_html_group_li,
    get_html_subgroup_info,
    get_html_subtask_info,
    get_html_task_li,
)


def test_auth_link_super_admin_guest():
    user = User(username="root", is_super_admin=True, is_guest=True)
    assert get_html_auth_link(user) == "Hi, root"


def test_auth_link_plain_guest_shows_login():
    user = User(username="anon", is_guest=True, is_super_admin=False)
    html = get_html_auth_link(user)
    assert "Login" in html
    assert 'href="/login"' in html
    assert "anon" in html


def test_auth_link_logged_in_shows_logout():
    user = User(username="alice", is_guest=False, is_super_admin=False)
    html = get_html_auth_link(user)
    assert "Logout" in html
    assert 'href="/logout"' in html
    assert "alice" in html


def _mk_task(name: str, description: str = "desc"):
    task = MagicMock()
    task.name = name
    task.description = description
    return task


def _mk_group(description: str = "group-desc"):
    group = MagicMock()
    group.description = description
    return group


def test_task_li_appends_trailing_slash_when_missing():
    task = _mk_task("run", "Run the thing")
    html = get_html_task_li("/api/group", "run", task)
    assert html == '<li><a href="/api/group/run">run</a> Run the thing</li>'


def test_task_li_keeps_existing_trailing_slash():
    task = _mk_task("run", "Run the thing")
    html = get_html_task_li("/api/group/", "run", task)
    assert html == '<li><a href="/api/group/run">run</a> Run the thing</li>'


def test_group_li_appends_trailing_slash_when_missing():
    group = _mk_group("Project group")
    html = get_html_group_li("/api", "proj", group)
    assert html == '<li><a href="/api/proj">proj</a> Project group</li>'


def test_subtask_info_empty_returns_empty_string():
    user = User(username="u", is_super_admin=True)
    group = _mk_group()
    # No subtasks — internal helper returns {}
    import zrb.runner.web_util.html as html_mod

    orig = html_mod.get_subtasks
    html_mod.get_subtasks = lambda *a, **kw: {}
    try:
        assert get_html_subtask_info(user, "/api", group) == ""
    finally:
        html_mod.get_subtasks = orig


def test_subtask_info_renders_when_accessible():
    user = User(username="u", is_super_admin=True)
    group = _mk_group()
    task = _mk_task("run", "Do thing")
    import zrb.runner.web_util.html as html_mod

    orig = html_mod.get_subtasks
    html_mod.get_subtasks = lambda *a, **kw: {"run": task}
    try:
        html = get_html_subtask_info(user, "/api", group)
        assert "<h5>Tasks</h5>" in html
        assert "Do thing" in html
    finally:
        html_mod.get_subtasks = orig


def test_subgroup_info_empty_returns_empty_string():
    user = User(username="u", is_super_admin=True)
    group = _mk_group()
    import zrb.runner.web_util.html as html_mod

    orig = html_mod.get_non_empty_subgroups
    html_mod.get_non_empty_subgroups = lambda *a, **kw: {}
    try:
        assert get_html_subgroup_info(user, "/api", group) == ""
    finally:
        html_mod.get_non_empty_subgroups = orig


def test_subgroup_info_renders_when_accessible():
    user = User(username="u", is_super_admin=True)
    parent = _mk_group()
    child = _mk_group("Child group")
    import zrb.runner.web_util.html as html_mod

    orig = html_mod.get_non_empty_subgroups
    html_mod.get_non_empty_subgroups = lambda *a, **kw: {"child": child}
    try:
        html = get_html_subgroup_info(user, "/api", parent)
        assert "<h5>Groups</h5>" in html
        assert "Child group" in html
    finally:
        html_mod.get_non_empty_subgroups = orig
