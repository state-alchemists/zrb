from unittest import mock

from zrb.context.shared_context import SharedContext
from zrb.input.password_input import PasswordInput


def test_password_input_to_html():
    password_input = PasswordInput(
        name="my_password",
        description="My password input",
        default="my-secret",
    )
    shared_ctx = SharedContext(env={})
    html = password_input.to_html(shared_ctx)
    assert 'type="password"' in html
    assert 'name="my_password"' in html
    assert 'placeholder="My password input"' in html
    assert 'value="my-secret"' in html


@mock.patch("getpass.getpass")
def test_password_input_prompt_cli_str(mock_getpass):
    mock_getpass.return_value = "user-input"
    password_input = PasswordInput(
        name="my_password",
        prompt="Enter your password",
        default="default-pass",
    )
    shared_ctx = SharedContext(env={})
    value = password_input._prompt_cli_str(shared_ctx)
    assert value == "user-input"
    mock_getpass.assert_called_with("Enter your password: ")


@mock.patch("getpass.getpass")
def test_password_input_prompt_cli_str_empty_uses_default(mock_getpass):
    mock_getpass.return_value = ""
    password_input = PasswordInput(
        name="my_password",
        prompt="Enter your password",
        default="default-pass",
    )
    shared_ctx = SharedContext(env={})
    value = password_input._prompt_cli_str(shared_ctx)
    assert value == "default-pass"
    mock_getpass.assert_called_with("Enter your password: ")
