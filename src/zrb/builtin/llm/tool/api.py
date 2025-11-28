from typing import Any, Callable, Literal

from zrb.config.llm_config import llm_config


def create_get_current_location() -> Callable:
    if llm_config.default_current_location_tool is not None:
        return llm_config.default_current_location_tool

    def get_current_location() -> dict[str, float]:
        """
        Gets the user's current geographical location (latitude and longitude).

        Example:
        get_current_location() # Returns {'lat': 48.8584, 'lon': 2.2945}

        Returns:
            dict: Dictionary with 'lat' and 'lon' keys.
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
        Gets current weather conditions for a given location.

        Example:
        get_current_weather(
            latitude=34.0522, longitude=-118.2437, temperature_unit='fahrenheit'
        )

        Args:
            latitude (float): Latitude of the location.
            longitude (float): Longitude of the location.
            temperature_unit (Literal): 'celsius' or 'fahrenheit'.

        Returns:
            dict: Detailed weather data.
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
