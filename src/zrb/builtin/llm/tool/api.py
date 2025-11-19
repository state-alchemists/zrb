from typing import Any, Callable, Literal

from zrb.config.llm_config import llm_config


def create_get_current_location() -> Callable:
    if llm_config.default_current_location_tool is not None:
        return llm_config.default_current_location_tool

    def get_current_location() -> dict[str, float]:
        """
        Fetches the user's current geographical location based on their IP address.

        Use when user asks "Where am I?", "What is my current location?", or has query requiring location.

        Returns:
            dict[str, float]: Dictionary containing 'lat' and 'lon' of current location.
                Example: {"lat": 48.8584, "lon": 2.2945}
        Raises:
            requests.RequestException: If API request to location service fails
        """
        import requests

        try:
            response = requests.get("http://ip-api.com/json?fields=lat,lon", timeout=5)
            response.raise_for_status()
            return dict(response.json())
        except requests.RequestException as e:
            raise requests.RequestException(f"Failed to get location: {e}")

    return get_current_location


def create_get_current_weather() -> Callable:
    if llm_config.default_current_weather_tool is not None:
        return llm_config.default_current_weather_tool

    def get_current_weather(
        latitude: float,
        longitude: float,
        temperature_unit: Literal["celsius", "fahrenheit"],
    ) -> dict[str, Any]:
        """
        Retrieves the current weather conditions for a given geographical location.

        Use when user asks about weather. If no location provided, use `get_current_location` first.

        Args:
            latitude (float): Latitude of the location
            longitude (float): Longitude of the location
            temperature_unit (Literal["celsius", "fahrenheit"]): Desired unit for temperature reading

        Returns:
            dict[str, Any]: Dictionary containing detailed weather data including temperature, wind speed, and weather code
        Raises:
            requests.RequestException: If API request to weather service fails
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
            return dict(response.json())
        except requests.RequestException as e:
            raise requests.RequestException(f"Failed to get weather data: {e}")

    return get_current_weather
