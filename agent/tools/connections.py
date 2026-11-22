"""get_connections: the train connections from one city to another on one day."""

from ..data_service import DataService
from . import args

NAME = "get_connections"


def definition(data: DataService) -> dict:
    """Name, purpose and parameters as the model sees them (OpenAI tool format)."""
    return {
        "type": "function",
        "function": {
            "name": NAME,
            "description": (
                "Returns the train connections from one city to another on one day: train, departure "
                "and arrival time, number of changes and price in EUR. Use it for questions about how "
                "to get somewhere, trains, departures or travel times. "
                + " ".join(filter(None, (data.describe_cities(), data.describe_routes())))
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "from": {"type": "string", "description": "City code of departure, e.g. ulm."},
                    "to": {"type": "string", "description": "City code of arrival, e.g. muenchen."},
                    "date": {
                        "type": "string",
                        "description": "The day of travel, formatted as YYYY-MM-DD, e.g. 2026-10-29.",
                    },
                },
                "required": ["from", "to", "date"],
                "additionalProperties": False,
            },
        },
    }


def run(arguments: dict, data: DataService) -> dict:
    day = args.day(arguments)
    origin_name, destination_name = args.text(arguments, "from"), args.text(arguments, "to")
    origin, destination = data.city_code(origin_name), data.city_code(destination_name)
    if origin is None:
        return data.unknown_city(origin_name, date=day)
    if destination is None:
        return data.unknown_city(destination_name, date=day)
    if origin == destination:
        raise args.ToolInputError("'from' and 'to' are the same city")
    return data.get(
        "transit",
        origin,
        destination,
        day,
        about={"from": origin, "to": destination, "date": day},
        no_data="There are no train connections for this route and day, so they are unknown.",
    )
