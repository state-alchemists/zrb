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



