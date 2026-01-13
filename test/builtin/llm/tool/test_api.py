from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.llm.tool.api import (
    create_get_current_location,
    create_get_current_weather,
)


def test_get_current_location():
    tool = create_get_current_location()

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"lat": 1.0, "lon": 2.0}
        mock_get.return_value = mock_response

        result = tool()
        assert result == {"lat": 1.0, "lon": 2.0}
        mock_get.assert_called_with("http://ip-api.com/json?fields=lat,lon", timeout=5)


def test_get_current_location_error():
    tool = create_get_current_location()

    with patch("requests.get") as mock_get:
        # Simulate request exception
        import requests

        mock_get.side_effect = requests.RequestException("Boom")

        with pytest.raises(requests.RequestException):
            tool()


def test_get_current_weather():
    tool = create_get_current_weather()

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"temperature": 25}
        mock_get.return_value = mock_response

        result = tool(latitude=10.0, longitude=20.0, temperature_unit="celsius")
        assert result == {"temperature": 25}
        mock_get.assert_called()


def test_get_current_weather_error():
    tool = create_get_current_weather()

    with patch("requests.get") as mock_get:
        import requests

        mock_get.side_effect = requests.RequestException("Boom")

        with pytest.raises(requests.RequestException):
            tool(latitude=10.0, longitude=20.0, temperature_unit="celsius")
