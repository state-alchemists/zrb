"""`zrb server start`: app wiring, and the security gate on the bind address.

Split from `test_cli.py` by feature group: everything here drives the
`server start` task, and the bulk of it pins `_refuse_insecure_bind` -- which
combination of host, auth flag and credentials is allowed to serve, and which
must exit non-zero before the app is even built.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_start_server_task_builds_and_serves_app():
    """`server start` wires up the web app and awaits the uvicorn server."""
    from zrb.runner.cli import cli

    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("uvicorn.Config") as mock_config,
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app") as mock_create,
        patch("zrb.runner.web_app.configure_uvicorn_logging") as mock_log,
    ):
        cli.run(str_args=["server", "start"])

    mock_log.assert_called_once()
    mock_create.assert_called_once()
    mock_config.assert_called_once()
    assert mock_config.call_args.kwargs["host"] == "127.0.0.1"
    mock_server.serve.assert_awaited_once()


def test_start_server_refuses_insecure_bind(monkeypatch, capsys):
    """Non-loopback host + auth off must fail closed, never start."""
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("ZRB_WEB_AUTH_ENABLED", "0")
    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("uvicorn.Config"),
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app") as mock_create,
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli.run(str_args=["server", "start"])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Refusing to bind" in err
    assert "without authentication" in err
    # The app is never even built, let alone served.
    mock_create.assert_not_called()
    mock_server.serve.assert_not_awaited()


def test_start_server_refuses_default_credentials_when_auth_enabled(
    monkeypatch, capsys
):
    """Auth being *on* is not enough: the default password/secret are public
    knowledge (documented in the repo), so a non-loopback bind still using
    them fails closed too, distinctly from the unauthenticated case."""
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("ZRB_WEB_AUTH_ENABLED", "1")
    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("uvicorn.Config"),
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app"),
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli.run(str_args=["server", "start"])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Refusing to bind" in err
    assert "without authentication" not in err
    assert "WEB_SUPER_ADMIN_PASSWORD" in err
    assert "WEB_SECRET_KEY" in err
    mock_server.serve.assert_not_awaited()


def test_start_server_uses_programmatic_auth_config_for_refusal(monkeypatch, capsys):
    """Refusal follows the auth object used by the web app, not only CFG.

    CFG says auth is on here; the programmatic object says it is off. The
    object wins, because it is what the running app will actually enforce.
    """
    from zrb.config.web_auth_config import WebAuthConfig
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("ZRB_WEB_AUTH_ENABLED", "1")
    auth_config = WebAuthConfig(enable_auth=False)
    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("zrb.runner.cli.web_auth_config", auth_config),
        patch("uvicorn.Config"),
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app"),
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli.run(str_args=["server", "start"])

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "Refusing to bind" in err
    assert "without authentication" in err
    mock_server.serve.assert_not_awaited()


def test_start_server_allows_programmatic_custom_credentials(monkeypatch, capsys):
    """Programmatic auth overrides are evaluated instead of CFG defaults.

    CFG says auth is off, which would refuse; the programmatic object supplies
    auth plus unique credentials, so the bind is allowed.
    """
    from zrb.config.web_auth_config import WebAuthConfig
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("ZRB_WEB_AUTH_ENABLED", "0")
    auth_config = WebAuthConfig(
        enable_auth=True,
        super_admin_password="programmatic-password",
        secret_key="programmatic-secret-key-32-chars-ok",
    )
    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("zrb.runner.cli.web_auth_config", auth_config),
        patch("uvicorn.Config"),
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app"),
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
    ):
        cli.run(str_args=["server", "start"])

    err = capsys.readouterr().err
    assert "without authentication" not in err
    assert "still has its default" not in err
    mock_server.serve.assert_awaited_once()


def test_start_server_allows_auth_enabled_with_custom_credentials(monkeypatch, capsys):
    """A public bind starts cleanly once auth is on AND the defaults changed."""
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("ZRB_WEB_AUTH_ENABLED", "1")
    monkeypatch.setenv("ZRB_WEB_SUPER_ADMIN_PASSWORD", "a-unique-password")
    monkeypatch.setenv("ZRB_WEB_SECRET_KEY", "a-unique-secret-key-of-32-chars-x")
    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("uvicorn.Config"),
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app"),
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
    ):
        cli.run(str_args=["server", "start"])

    err = capsys.readouterr().err
    assert "without authentication" not in err
    assert "still has its default" not in err


@pytest.mark.parametrize(
    "password, secret_key, expected_fragment",
    [
        ("", "a-long-enough-secret-key-of-32-ch", "WEB_SUPER_ADMIN_PASSWORD is empty"),
        (
            "   ",
            "a-long-enough-secret-key-of-32-ch",
            "WEB_SUPER_ADMIN_PASSWORD is empty",
        ),
        ("a-long-enough-password", "", "WEB_SECRET_KEY is empty"),
        (
            "short",
            "a-long-enough-secret-key-of-32-ch",
            "WEB_SUPER_ADMIN_PASSWORD is shorter",
        ),
        ("a-long-enough-password", "too-short", "WEB_SECRET_KEY is shorter"),
    ],
)
def test_start_server_refuses_unusable_programmatic_credentials(
    monkeypatch, capsys, password, secret_key, expected_fragment
):
    """Non-default is not the same as usable.

    `WebAuthConfig` treats only `None` as "fall back to CFG", so an explicit
    empty string is a real override that no longer equals the shipped default —
    it would sail past a check that only asked whether the value had changed,
    leaving a public server behind no password at all. Length floors apply for
    the same reason: `"a"` is not the documented default either.
    """
    from zrb.config.web_auth_config import WebAuthConfig
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", "0.0.0.0")
    auth_config = WebAuthConfig(
        enable_auth=True, super_admin_password=password, secret_key=secret_key
    )
    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("zrb.runner.cli.web_auth_config", auth_config),
        patch("uvicorn.Config"),
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app") as mock_create,
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli.run(str_args=["server", "start"])

    assert exc_info.value.code == 1
    assert expected_fragment in capsys.readouterr().err
    mock_create.assert_not_called()
    mock_server.serve.assert_not_awaited()


def test_start_server_reports_every_credential_problem_at_once(monkeypatch, capsys):
    """Both bad credentials are listed, so one fix does not reveal the next."""
    from zrb.config.web_auth_config import WebAuthConfig
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", "0.0.0.0")
    auth_config = WebAuthConfig(
        enable_auth=True, super_admin_password="", secret_key=""
    )
    with (
        patch("zrb.runner.cli.web_auth_config", auth_config),
        patch("uvicorn.Config"),
        patch("uvicorn.Server"),
        patch("zrb.runner.web_app.create_web_app"),
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
        pytest.raises(SystemExit),
    ):
        cli.run(str_args=["server", "start"])

    err = capsys.readouterr().err
    assert "WEB_SUPER_ADMIN_PASSWORD is empty" in err
    assert "WEB_SECRET_KEY is empty" in err


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "127.0.0.2", "::1", "0:0:0:0:0:0:0:1", "localhost", "LOCALHOST"],
)
def test_start_server_allows_every_spelling_of_loopback(monkeypatch, host):
    """Loopback is decided by parsing the address, not by string equality.

    Exact matching rejected `0:0:0:0:0:0:0:1` and `127.0.0.2`, which bind to
    loopback and nothing else, while auth was off — an availability regression
    with no security benefit.
    """
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", host)
    monkeypatch.setenv("ZRB_WEB_AUTH_ENABLED", "0")
    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("uvicorn.Config"),
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app"),
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
    ):
        cli.run(str_args=["server", "start"])

    mock_server.serve.assert_awaited_once()


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.10", "example.com"])
def test_start_server_treats_unprovable_hosts_as_exposed(monkeypatch, host):
    """A name that cannot be proven loopback-only fails closed."""
    from zrb.runner.cli import cli

    monkeypatch.setenv("ZRB_WEB_HTTP_HOST", host)
    monkeypatch.setenv("ZRB_WEB_AUTH_ENABLED", "0")
    with (
        patch("uvicorn.Config"),
        patch("uvicorn.Server"),
        patch("zrb.runner.web_app.create_web_app"),
        patch("zrb.runner.web_app.configure_uvicorn_logging"),
        pytest.raises(SystemExit),
    ):
        cli.run(str_args=["server", "start"])
