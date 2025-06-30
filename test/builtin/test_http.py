import shlex
import unittest
from unittest.mock import MagicMock, patch

from zrb.builtin.http import generate_curl, http_request
from zrb.task.base_task import BaseTask


class TestBuiltinHttp(unittest.TestCase):
    def test_http_request(self):
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

    def test_generate_curl(self):
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
            "Content-Type: application/json",
            "--data-raw",
            '{"foo": "bar"}',
            "--insecure",
            "https://example.com",
        ]
        result_parts = shlex.split(result)
        # shlex.split may split the header, so we need to rejoin it
        for i, part in enumerate(result_parts):
            if part == "Content-Type:":
                result_parts[i] = f"{part} {result_parts.pop(i+1)}"
        self.assertEqual(result_parts, expected_parts)


if __name__ == "__main__":
    unittest.main()
