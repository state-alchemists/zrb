import shlex
from unittest.mock import MagicMock, patch

from zrb.builtin.http import generate_curl, http_request
from zrb.task.base_task import BaseTask


def test_http_request():
    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = '{"foo": "bar"}'
        mock_request.return_value = mock_response

        task: BaseTask = http_request
        task.run(
            str_kwargs={
                "method": "GET",
                "url": "https://example.com",
                "headers": "{}",
                "body": "{}",
                "verify_ssl": "true",
            }
        )
        mock_request.assert_called_with(
            method="GET",
            url="https://example.com",
            headers={},
            json=None,
            verify=True,
        )


def test_generate_curl():
    task: BaseTask = generate_curl
    result = task.run(
        str_kwargs={
            "method": "POST",
            "url": "https://example.com",
            "headers": '{"Content-Type": "application/json"}',
            "body": '{"foo": "bar"}',
            "verify_ssl": "false",
        }
    )
    expected_parts = [
        "curl",
        "-X",
        "POST",
        "-H",
        "Content-Type:",
        "application/json",
        "--data-raw",
        '{"foo": "bar"}',
        "--insecure",
        "https://example.com",
    ]
    assert shlex.split(result) == expected_parts
