import unittest
from unittest.mock import patch

from zrb.builtin.jwt import decode_jwt, encode_jwt, validate_jwt
from zrb.task.base_task import BaseTask


class TestBuiltinJwt(unittest.TestCase):
    def test_encode_jwt(self):
        task: BaseTask = encode_jwt
        token = task.run(
            str_kwargs={
                "secret": "secret",
                "payload": '{"foo": "bar"}',
                "algorithm": "HS256",
            }
        )
        self.assertIsInstance(token, str)

    def test_decode_jwt(self):
        task: BaseTask = encode_jwt
        token = task.run(
            str_kwargs={
                "secret": "secret",
                "payload": '{"foo": "bar"}',
                "algorithm": "HS256",
            }
        )
        task: BaseTask = decode_jwt
        payload = task.run(
            str_kwargs={"token": token, "secret": "secret", "algorithm": "HS256"}
        )
        self.assertEqual(payload, {"foo": "bar"})

    def test_validate_jwt(self):
        task: BaseTask = encode_jwt
        token = task.run(
            str_kwargs={
                "secret": "secret",
                "payload": '{"foo": "bar"}',
                "algorithm": "HS256",
            }
        )
        task: BaseTask = validate_jwt
        is_valid = task.run(
            str_kwargs={"token": token, "secret": "secret", "algorithm": "HS256"}
        )
        self.assertTrue(is_valid)


if __name__ == "__main__":
    unittest.main()
