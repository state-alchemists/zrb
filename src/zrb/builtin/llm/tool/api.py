import json
import requests
from typing import Annotated, Literal

# Constants
DEFAULT_TIMEOUT = 10  # seconds


def get_current_location() -> Annotated[
    str, "JSON string representing latitude and longitude"
]:
    """
    Get the user's current location based on IP address.
    
    Returns:
        JSON string containing latitude and longitude
        
    Raises:
        ConnectionError: If API request fails
    """
    try:
        response = requests.get(
            "http://ip-api.com/json?fields=lat,lon",
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Location API error: {str(e)}")


def get_current_weather(
    latitude: float,
    longitude: float,
    temperature_unit: Literal["celsius", "fahrenheit"],
) -> str:
    """
    Get the current weather for a specific location.
    
    Args:
        latitude: The latitude coordinate
        longitude: The longitude coordinate
        temperature_unit: Unit for temperature measurement ("celsius" or "fahrenheit")
        
    Returns:
        JSON string with current weather data
        
    Raises:
        ValueError: If coordinates are invalid
        ConnectionError: If weather API request fails
    """
    # Basic validation of coordinates
    if not (-90 <= latitude <= 90):
        raise ValueError(f"Invalid latitude: {latitude}. Must be between -90 and 90.")
        
    if not (-180 <= longitude <= 180):
        raise ValueError(f"Invalid longitude: {longitude}. Must be between -180 and 180.")
    
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "temperature_unit": temperature_unit,
                "current_weather": True,
            },
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Weather API error: {str(e)}")
