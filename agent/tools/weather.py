"""get_weather: the weather forecast for one city on one day."""

from ..data_service import DataService
from . import args

NAME = "get_weather"


def definition(data: DataService) -> dict:
    """Name, purpose and parameters as the model sees them (OpenAI tool format)."""
    return {
        "type": "function",
        "function": {
            "name": NAME,
            "description": (
                "Returns the weather forecast for one city on one day: condition, temperature in °C, "
                "probability of rain from 0 to 1, and wind in km/h. Use it for questions about the "
                "weather, rain, an umbrella or what to wear. " + data.describe_cities()
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City code, e.g. muenchen."},
                    "date": {
                        "type": "string",
                        "description": "The day, formatted as YYYY-MM-DD, e.g. 2026-10-29.",
                    },
                },
                "required": ["city", "date"],
                "additionalProperties": False,
            },
        },
    }


def run(arguments: dict, data: DataService) -> dict:
    day = args.day(arguments)
    name = args.text(arguments, "city")
    city = data.city_code(name)
    if city is None:
        return data.unknown_city(name, date=day)
    return data.get(
        "weather",
        city,
        day,
        about={"city": city, "date": day},
        no_data="There is no weather forecast for this city and day, so the weather is unknown.",
    )
