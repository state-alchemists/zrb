import os
from unittest import mock

import pytest

from zrb.builtin.llm import please as please_module
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


@pytest.fixture
def session():
    return Session(shared_ctx=SharedContext(), state_logger=mock.MagicMock())


class _FakeResult:

    def __init__(self, output: str):
        self.output = output


def _create_fake_agent(output: str) -> mock.MagicMock:
    agent = mock.MagicMock()
    agent.run = mock.AsyncMock(return_value=_FakeResult(output))
    return agent


def test_strip_code_fences_plain_command():
    assert please_module.strip_code_fences("ls -la") == "ls -la"


def test_strip_code_fences_with_language_tag():
    text = "```bash\nls -la\n```"
    assert please_module.strip_code_fences(text) == "ls -la"


def test_strip_code_fences_without_language_tag():
    text = "```\nGet-ChildItem\n```"
    assert please_module.strip_code_fences(text) == "Get-ChildItem"


def test_strip_code_fences_multiline_command():
    text = '```sh\ndocker ps --filter \\\n  "name=web"\n```'
    assert (
        please_module.strip_code_fences(text) == 'docker ps --filter \\\n  "name=web"'
    )


def test_strip_code_fences_surrounding_backticks():
    assert please_module.strip_code_fences("`git status`") == "git status"


def test_build_user_message_contains_intent_and_context():
    message = please_module.build_user_message("list all files")
    assert "Intent: list all files" in message
    assert f"- Working directory: {os.getcwd()}" in message
    assert "- Platform:" in message
    assert "- Shell:" in message


def test_get_platform_description():
    with mock.patch.object(please_module.platform, "system", return_value="Darwin"):
        assert please_module.get_platform_description() == "macOS"
    with mock.patch.object(please_module.platform, "system", return_value="Windows"):
        assert please_module.get_platform_description() == "Windows"


def test_get_platform_description_wsl():
    with mock.patch.object(please_module.platform, "system", return_value="Linux"):
        with mock.patch.object(please_module, "is_wsl", return_value=True):
            assert (
                please_module.get_platform_description()
                == "Linux (WSL, Windows commands available via interop)"
            )
        with mock.patch.object(please_module, "is_wsl", return_value=False):
            assert please_module.get_platform_description() == "Linux"


def test_build_user_message_reports_existing_shell(monkeypatch):
    monkeypatch.setattr(
        please_module, "get_current_shell", lambda: "zsh", raising=False
    )
    message = please_module.build_user_message("list all files")
    assert "- Shell: zsh" in message


@pytest.mark.asyncio
async def test_please_copies_command_to_clipboard(session):
    agent = _create_fake_agent("```bash\nls -la\n```")
    with mock.patch.object(please_module, "create_agent", return_value=agent):
        with mock.patch.object(
            please_module, "copy_text", return_value=True
        ) as copy_text_mock:
            result = await please_module.please.async_run(
                session=session,
                kwargs={"message": "list all files", "model": ""},
            )
    assert result == "ls -la"
    copy_text_mock.assert_called_once_with("ls -la")


@pytest.mark.asyncio
async def test_please_reports_empty_command(session):
    agent = _create_fake_agent("")
    with mock.patch.object(please_module, "create_agent", return_value=agent):
        result = await please_module.please.async_run(
            session=session,
            kwargs={"message": "impossible request", "model": ""},
        )
    assert result == ""


@pytest.mark.asyncio
async def test_please_succeeds_when_clipboard_unavailable(session):
    agent = _create_fake_agent("df -h")
    with mock.patch.object(please_module, "create_agent", return_value=agent):
        with mock.patch.object(please_module, "copy_text", return_value=False):
            result = await please_module.please.async_run(
                session=session,
                kwargs={"message": "show disk usage", "model": ""},
            )
    assert result == "df -h"
