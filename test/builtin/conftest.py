import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_uuid():
    with patch("uuid.uuid1", return_value="uuid1"), patch(
        "uuid.uuid3", return_value="uuid3"
    ), patch("uuid.uuid4", return_value="uuid4"), patch(
        "uuid.uuid5", return_value="uuid5"
    ), patch(
        "uuid.UUID"
    ) as mock_uuid_class:
        yield mock_uuid_class
