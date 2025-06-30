from zrb.builtin.jwt import decode_jwt, encode_jwt, validate_jwt
from zrb.task.base_task import BaseTask


def test_encode_jwt():
    task: BaseTask = encode_jwt
    token = task.run(
        str_kwargs={
            "secret": "secret",
            "payload": '{"foo": "bar"}',
            "algorithm": "HS256",
        }
    )
    assert isinstance(token, str)


def test_decode_jwt():
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
    assert payload == {"foo": "bar"}


def test_validate_jwt():
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
    assert is_valid
