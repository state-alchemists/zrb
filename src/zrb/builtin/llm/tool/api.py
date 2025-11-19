from typing import Any, Callable, Literal

from zrb.config.llm_config import llm_config


def create_get_current_location() -> Callable:
    if llm_config.default_current_location_tool is not None:
        return llm_config.default_current_location_tool

    def get_current_location() -> dict[str, float]:
        """
        Get the user's current geographical location (latitude and longitude) based on their IP address.

        Use when a user asks "Where am I?" or has a query that requires their current location.

        Returns:
            dict[str, float]: A dictionary containing 'lat' and 'lon' keys.
                Example: {"lat": 48.8584, "lon": 2.2945}
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
        Get the current weather conditions for a given latitude and longitude.

        Use when a user asks about the weather. If the location is not provided, use `get_current_location` first.

        Args:
            latitude (float): The latitude of the location.
            longitude (float): The longitude of the location.
            temperature_unit (Literal["celsius", "fahrenheit"]): The desired unit for the temperature reading.

        Returns:
            dict[str, Any]: A dictionary containing detailed weather data, including temperature, wind speed, and a weather code.
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
