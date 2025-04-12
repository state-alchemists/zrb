import json
from typing import Literal


def get_current_location() -> str:
    """Get current location (latitude, longitude) based on IP address.
    Returns:
        str: JSON string representing latitude and longitude.
    Raises:
        requests.RequestException: If the API request fails.
    """
    import requests

    try:
        response = requests.get("http://ip-api.com/json?fields=lat,lon", timeout=5)
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.RequestException as e:
        raise requests.RequestException(f"Failed to get location: {e}") from None


def get_current_weather(
    latitude: float,
    longitude: float,
    temperature_unit: Literal["celsius", "fahrenheit"],
) -> str:
    """Get current weather for a specific location.
    Args:
        latitude (float): Latitude coordinate.
        longitude (float): Longitude coordinate.
        temperature_unit (Literal["celsius", "fahrenheit"]): Temperature unit.
    Returns:
        str: JSON string with weather data.
    Raises:
        requests.RequestException: If the API request fails.
    """
    import requests

    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "temperature_unit": temperature_unit,
                "current_weather": True,
            },
            timeout=5,
        )
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.RequestException as e:
        raise requests.RequestException(f"Failed to get weather data: {e}") from None
