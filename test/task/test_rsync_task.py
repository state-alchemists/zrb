from unittest import mock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.task.rsync_task import RsyncTask


@pytest.mark.asyncio
@mock.patch("zrb.task.cmd_task.CmdTask._exec_action")
async def test_rsync_task_local_to_remote(mock_exec_action):
    rsync_task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
    )
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_rsync",
        color=1,
        icon="🔄",
    )
    await rsync_task._exec_action(ctx)
    assert (
        rsync_task._get_cmd_script(ctx)
        == 'rsync --mkpath -avz -e "ssh -p 22" /local/path remote-user@remote-host:/remote/path'
    )


@pytest.mark.asyncio
@mock.patch("zrb.task.cmd_task.CmdTask._exec_action")
async def test_rsync_task_remote_to_local(mock_exec_action):
    rsync_task = RsyncTask(
        name="test_rsync",
        remote_source_path="/remote/path",
        local_destination_path="/local/path",
        remote_host="remote-host",
        remote_user="remote-user",
    )
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_rsync",
        color=1,
        icon="🔄",
    )
    await rsync_task._exec_action(ctx)
    assert (
        rsync_task._get_cmd_script(ctx)
        == 'rsync --mkpath -avz -e "ssh -p 22" remote-user@remote-host:/remote/path /local/path'
    )


@pytest.mark.asyncio
@mock.patch("zrb.task.cmd_task.CmdTask._exec_action")
async def test_rsync_task_with_key(mock_exec_action):
    rsync_task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        remote_ssh_key="/path/to/key",
    )
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_rsync",
        color=1,
        icon="🔄",
    )
    await rsync_task._exec_action(ctx)
    assert (
        rsync_task._get_cmd_script(ctx)
        == 'rsync --mkpath -avz -e "ssh -i /path/to/key -p 22" /local/path remote-user@remote-host:/remote/path'
    )


@pytest.mark.asyncio
@mock.patch("zrb.task.cmd_task.CmdTask._exec_action")
async def test_rsync_task_with_password(mock_exec_action):
    rsync_task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        remote_password="password",
    )
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_rsync",
        color=1,
        icon="🔄",
    )
    await rsync_task._exec_action(ctx)
    assert (
        rsync_task._get_cmd_script(ctx)
        == 'sshpass -p "$_ZRB_SSH_PASSWORD" rsync --mkpath -avz -e "ssh -p 22" /local/path remote-user@remote-host:/remote/path'
    )


@pytest.mark.asyncio
@mock.patch("zrb.task.cmd_task.CmdTask._exec_action")
async def test_rsync_task_with_key_and_password(mock_run_cmd):
    rsync_task = RsyncTask(
        name="test_rsync",
        local_source_path="/local/path",
        remote_destination_path="/remote/path",
        remote_host="remote-host",
        remote_user="remote-user",
        remote_ssh_key="/path/to/key",
        remote_password="password",
    )
    shared_ctx = SharedContext(env={})
    ctx = Context(
        shared_ctx=shared_ctx,
        task_name="test_rsync",
        color=1,
        icon="🔄",
    )
    await rsync_task._exec_action(ctx)
    assert (
        rsync_task._get_cmd_script(ctx)
        == 'sshpass -p "$_ZRB_SSH_PASSWORD" rsync --mkpath -avz -e "ssh -i /path/to/key -p 22" /local/path remote-user@remote-host:/remote/path'
    )
