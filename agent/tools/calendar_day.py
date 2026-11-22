"""get_calendar_day: the appointments of one day."""

from ..data_service import DataService
from . import args

NAME = "get_calendar_day"


def definition(data: DataService) -> dict:
    """Name, purpose and parameters as the model sees them (OpenAI tool format)."""
    return {
        "type": "function",
        "function": {
            "name": NAME,
            "description": (
                "Returns all calendar appointments of one single day: title, start and end time, "
                "whether it is an all-day event, and location. Use it for every question about what "
                "is scheduled on a date. For questions about several days, call it once per day. "
                "An empty 'events' list means the day has no appointments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The day to look up, formatted as YYYY-MM-DD, e.g. 2026-10-29.",
                    },
                },
                "required": ["date"],
                "additionalProperties": False,
            },
        },
    }


def run(arguments: dict, data: DataService) -> dict:
    day = args.day(arguments)
    return data.get(
        "calendar",
        day,
        about={"date": day},
        no_data="The calendar has no data for this day, so it is unknown what is scheduled.",
    )
