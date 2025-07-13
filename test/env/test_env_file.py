from unittest import mock

from zrb.context.shared_context import SharedContext
from zrb.env.env_file import EnvFile


@mock.patch("zrb.env.env_file.dotenv_values")
def test_env_file(mock_dotenv_values):
    mock_dotenv_values.return_value = {"key1": "value1", "key2": "value2"}
    env_file = EnvFile(path="test.env")
    shared_ctx = SharedContext(env={})
    env_file.update_context(shared_ctx)
    assert shared_ctx.env["key1"] == "value1"
    assert shared_ctx.env["key2"] == "value2"
    mock_dotenv_values.assert_called_with("test.env")
