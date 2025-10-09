from typing import Any, Callable, Literal

from zrb.config.llm_config import llm_config


def create_get_current_location() -> Callable:
    if llm_config.default_current_location_tool is not None:
        return llm_config.default_current_location_tool

    def get_current_location() -> dict[str, float]:
        """
        Fetches the user's current geographical location based on their IP address.

        Use this tool when the user asks "Where am I?", "What is my current
        location?", or has a query that requires knowing their location to be
        answered.

        Returns:
            dict[str, float]: A dictionary containing the 'lat' and 'lon' of the current
                location.
                Example: {"lat": 48.8584, "lon": 2.2945}
        Raises:
            requests.RequestException: If the API request to the location service
                fails.
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

        Use this tool when the user asks about the weather. If the user does not
        provide a location, first use the `get_current_location` tool to
        determine their location.

        Args:
            latitude (float): The latitude of the location.
            longitude (float): The longitude of the location.
            temperature_unit (Literal["celsius", "fahrenheit"]): The desired unit
                for the temperature reading.

        Returns:
            dict[str, Any]: A dictionary containing detailed weather data, including
                temperature, wind speed, and weather code.
        Raises:
            requests.RequestException: If the API request to the weather service
                fails.
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
