import warnings
from functools import partial

import pytest

from zrb.attr.tpl import Tpl
from zrb.cmd.cmd_result import CmdResult
from zrb.cmd.cmd_val import Cmd
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.cmd_task import CmdTask, UntemplatedCmdWarning


@pytest.fixture
def mock_session():
    shared_ctx = SharedContext(logging_level=20)
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_cmd_task_exec_success(mock_session):
    """Successful command execution returns its result."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")

    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="test_cmd", cmd="echo hello")
        mock_session.register_task(task)

        result = await task.exec(mock_session)

        assert result == mock_cmd_result
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_failure(mock_session):
    """Failed commands raise."""
    mock_cmd_result = CmdResult(output="", error="error", display="")

    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (mock_cmd_result, 1)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="test_cmd_fail", cmd="exit 1")
        mock_session.register_task(task)

        with pytest.raises(RuntimeError, match="Process test_cmd_fail exited \\(1\\)"):
            await task.exec(mock_session)
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_failure_carries_task_context_note(mock_session):
    """CmdTask errors carry BaseTask's "Task: name (file:line)" note."""
    mock_cmd_result = CmdResult(output="", error="error", display="")

    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (mock_cmd_result, 1)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="test_cmd_fail_note", cmd="exit 1")
        mock_session.register_task(task)

        with pytest.raises(RuntimeError) as exc_info:
            await task.exec(mock_session)

        notes = getattr(exc_info.value, "__notes__", [])
        assert any("Task: test_cmd_fail_note" in note for note in notes)
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_signal_killed(mock_session):
    """Negative return code (signal-killed) must raise (regression)."""
    mock_cmd_result = CmdResult(output="", error="killed", display="")

    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (mock_cmd_result, -9)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="test_cmd_killed", cmd="sleep 100")
        mock_session.register_task(task)

        with pytest.raises(
            RuntimeError, match="Process test_cmd_killed exited \\(-9\\)"
        ):
            await task.exec(mock_session)
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_plain_print(mock_session):
    """`plain_print=True` reaches command execution."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")

    call_args_list = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="test_plain_print", cmd="echo plain", plain_print=True)
        mock_session.register_task(task)

        await task.exec(mock_session)

        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        print_method = call_kwargs["print_method"]
        assert isinstance(print_method, partial)
        assert print_method.keywords.get("plain") is True
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_exec_cwd(mock_session):
    """A custom working directory reaches execution."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")
    custom_cwd = "/tmp/custom_dir"

    call_args_list = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    import os

    original_abspath = os.path.abspath
    os.path.abspath = lambda x: x
    try:
        task = CmdTask(name="test_cwd", cmd="pwd", cwd=custom_cwd)
        mock_session.register_task(task)

        await task.exec(mock_session)

        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        assert call_kwargs["cwd"] == custom_cwd
    finally:
        zrb.task.cmd_task.run_command = original_run_command
        os.path.abspath = original_abspath


@pytest.mark.asyncio
async def test_cmd_task_exec_env(mock_session):
    """Custom environment variables reach execution."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")

    call_args_list = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        mock_session.shared_ctx.env["MY_VAR"] = "my_value"
        task = CmdTask(name="test_env", cmd="echo $MY_VAR")
        mock_session.register_task(task)

        await task.exec(mock_session)

        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        env_map = call_kwargs["env_map"]
        assert env_map["MY_VAR"] == "my_value"
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_local_run_does_not_export_sshpass(mock_session):
    """A local task must not leak its remote password into the child env, and
    unbuffered Python output uses the real PYTHONUNBUFFERED variable."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")
    call_args_list = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(
            name="test_local_secret",
            cmd="echo hi",
            remote_password="hunter2",
        )
        mock_session.register_task(task)
        await task.exec(mock_session)

        env_map = call_args_list[0][1]["env_map"]
        assert "SSHPASS" not in env_map
        assert env_map["PYTHONUNBUFFERED"] == "1"
    finally:
        zrb.task.cmd_task.run_command = original_run_command


@pytest.mark.asyncio
async def test_cmd_task_remote_with_password_exports_sshpass(mock_session):
    """Remote execution with a password needs SSHPASS for sshpass."""
    mock_cmd_result = CmdResult(output="output", error="", display="output")
    call_args_list = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    original_get_remote_cmd_script = zrb.task.cmd_task.get_remote_cmd_script
    zrb.task.cmd_task.run_command = mock_run_command
    zrb.task.cmd_task.get_remote_cmd_script = lambda *a, **k: "ssh-script"
    try:
        task = CmdTask(
            name="test_remote_secret",
            cmd="echo hi",
            remote_host="host",
            remote_user="user",
            remote_password="hunter2",
        )
        mock_session.register_task(task)
        await task.exec(mock_session)

        env_map = call_args_list[0][1]["env_map"]
        assert env_map["SSHPASS"] == "hunter2"
    finally:
        zrb.task.cmd_task.run_command = original_run_command
        zrb.task.cmd_task.get_remote_cmd_script = original_get_remote_cmd_script


@pytest.mark.asyncio
async def test_cmd_task_exec_remote(mock_session):
    """Remote command execution builds the remote invocation."""
    mock_cmd_result = CmdResult(
        output="remote output", error="", display="remote output"
    )

    call_args_list = []

    def mock_run_command(*args, **kwargs):
        async def _coro():
            call_args_list.append((args, kwargs))
            return (mock_cmd_result, 0)

        return _coro()

    import zrb.task.cmd_task

    original_run_command = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    original_get_remote_cmd_script = zrb.task.cmd_task.get_remote_cmd_script
    zrb.task.cmd_task.get_remote_cmd_script = lambda *a, **k: "ssh-script"
    try:
        task = CmdTask(
            name="test_remote",
            cmd="echo remote",
            remote_host="host",
            remote_user="user",
        )
        mock_session.register_task(task)

        await task.exec(mock_session)

        assert len(call_args_list) == 1
        call_kwargs = call_args_list[0][1]
        assert call_kwargs["cmd"][2] == "ssh-script"
    finally:
        zrb.task.cmd_task.run_command = original_run_command
        zrb.task.cmd_task.get_remote_cmd_script = original_get_remote_cmd_script


@pytest.mark.parametrize(
    "shell, should_warn",
    [
        ("bash", True),
        ("/bin/bash", True),
        # Windows supplies Git Bash as an `.exe` path.
        ("C:\\Program Files\\Git\\bin\\bash.exe", True),
        ("/usr/bin/zsh", True),
        ("cmd", False),
        ("C:\\Windows\\System32\\cmd.exe", False),
    ],
)
@pytest.mark.asyncio
async def test_cmd_task_warns_about_unrecommended_commands_by_shell_name(
    mock_session, shell, should_warn
):
    """The POSIX-command lint keys off the shell's *name*, so it survives an
    absolute path with an `.exe` suffix."""
    import zrb.task.cmd_task

    def mock_run_command(*args, **kwargs):
        async def _coro():
            return (CmdResult(output="", error="", display=""), 0)

        return _coro()

    original = zrb.task.cmd_task.run_command
    zrb.task.cmd_task.run_command = mock_run_command
    try:
        task = CmdTask(name="lint_shell", cmd="realpath .", shell=shell)
        mock_session.register_task(task)
        await task.exec(mock_session)
    finally:
        zrb.task.cmd_task.run_command = original

    # `shared_log` rather than captured stderr: it is the public, stream-
    # independent record of everything the task printed.
    log = "".join(mock_session.shared_ctx.shared_log)
    assert ("unrecommended commands" in log) is should_warn


# --- plain-string `cmd` with a `{ctx.` placeholder ---------------------------


def _placeholder_warnings(cmd) -> list:
    """`UntemplatedCmdWarning`s raised while building a task around `cmd`."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        CmdTask(name="greet", cmd=cmd)
    return [w for w in caught if issubclass(w.category, UntemplatedCmdWarning)]


def test_a_plain_string_cmd_with_a_placeholder_warns_and_names_the_fix():
    """The runtime half of the doc guard: a user's own `cmd`, not a doc fence.

    A bare string is a literal, so `cmd="echo {ctx.input.name}"` echoes the
    braces, exits 0, and is simply wrong. Nothing used to say so.
    """
    found = _placeholder_warnings("echo {ctx.input.name}")
    assert len(found) == 1
    message = str(found[0].message)
    assert "Tpl(" in message
    assert "`cmd`" in message


def test_the_warning_names_the_offending_entry_without_quoting_it():
    """A `cmd` can carry a credential, and this warning reaches stderr.

    It is raised at construction, before anything has decided to run the task,
    so it is not a command log a reader opted into. `redact_env_map` cannot be
    used here — it redacts by environment *name*, and a command string has no
    names to go by — so the command text has to stay out of the message, and the
    entry is identified by position instead.
    """
    secret = "sk-live-0123456789abcdef"
    found = _placeholder_warnings(f"curl -H 'Authorization: Bearer {secret}' {{ctx.input.url}}")
    assert len(found) == 1
    message = str(found[0].message)
    assert secret not in message
    assert "curl" not in message
    assert "Tpl(" in message
    assert "`cmd`" in message


def test_a_tpl_cmd_does_not_warn():
    """`Tpl` exists to render the placeholder; warning here reports the fix."""
    assert _placeholder_warnings(Tpl("echo {ctx.input.name}")) == []


def test_a_cmd_wrapper_does_not_warn():
    """`Cmd` resolves through the context, exactly like `Tpl`."""
    assert _placeholder_warnings(Cmd("echo {ctx.input.name}")) == []


def test_a_callable_cmd_does_not_warn():
    """A callable builds its string at run time, so there is nothing to read."""
    assert _placeholder_warnings(lambda ctx: "echo {ctx.input.name}") == []


def test_a_plain_string_of_shell_braces_does_not_warn():
    """`${VAR}` and `awk '{print}'` are shell syntax, not placeholders.

    Escaping those is the whole reason a bare string is a literal, so a warning
    here would be wrong about the feature it guards.
    """
    assert _placeholder_warnings("awk '{print $1}' && echo ${HOME}") == []


def test_a_placeholder_inside_a_list_of_commands_names_its_position():
    """The entry is identified by index, since its text is not quoted."""
    found = _placeholder_warnings(["echo hi", "echo {ctx.input.name}"])
    assert len(found) == 1
    message = str(found[0].message)
    assert "`cmd[1]`" in message
    assert "echo {ctx.input.name}" not in message


def test_a_list_of_tpls_does_not_warn():
    assert _placeholder_warnings([Tpl("echo {ctx.input.name}")]) == []


def test_the_warning_fires_once_per_call_site():
    """A task defined in a loop reports once, not once per iteration."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")
        for _ in range(3):
            CmdTask(name="greet", cmd="echo {ctx.input.name}")
    found = [w for w in caught if issubclass(w.category, UntemplatedCmdWarning)]
    assert len(found) == 1
