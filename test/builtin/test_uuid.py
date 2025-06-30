from unittest.mock import patch

from zrb.builtin.uuid import (
    generate_uuid_v1,
    generate_uuid_v3,
    generate_uuid_v4,
    generate_uuid_v5,
    validate_uuid,
)
from zrb.task.base_task import BaseTask


def test_generate_uuid_v1():
    with patch("uuid.uuid1", return_value="uuid1"):
        task: BaseTask = generate_uuid_v1
        result = task.run()
        assert result == "uuid1"


def test_generate_uuid_v3():
    with patch("uuid.uuid3", return_value="uuid3"):
        task: BaseTask = generate_uuid_v3
        result = task.run(str_kwargs={"namespace": "dns", "name": "example.com"})
        assert result == "uuid3"


def test_generate_uuid_v4():
    with patch("uuid.uuid4", return_value="uuid4"):
        task: BaseTask = generate_uuid_v4
        result = task.run()
        assert result == "uuid4"


def test_generate_uuid_v5():
    with patch("uuid.uuid5", return_value="uuid5"):
        task: BaseTask = generate_uuid_v5
        result = task.run(str_kwargs={"namespace": "dns", "name": "example.com"})
        assert result == "uuid5"


def test_validate_uuid():
    with patch("uuid.UUID") as mock_uuid:
        task: BaseTask = validate_uuid
        is_valid = task.run(str_kwargs={"id": "some-uuid"})
        assert is_valid
        mock_uuid.assert_called_with("some-uuid", version=1)

        mock_uuid.side_effect = ValueError
        is_invalid = task.run(str_kwargs={"id": "invalid-uuid"})
        assert not is_invalid
