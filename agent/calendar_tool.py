"""The calendar tool: reads the appointments of one day from the mock data service."""

import json
import re
import urllib.error
import urllib.request
from datetime import date

NAME = "get_calendar_day"
TIMEOUT_SECONDS = 15

# Name, purpose and parameters as the model sees them (OpenAI tool format).
DEFINITION = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Returns all calendar appointments of one single day: title, start and end time, "
            "whether it is an all-day event, and location. Use it for every question about what is "
            "scheduled on a date. For questions about several days, call it once per day. "
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

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def day_url(data_base_url: str, day: str) -> str:
    return f"{data_base_url}/calendar/{day}.json"


def get_calendar_day(data_base_url: str, day: str) -> dict:
    """Fetch one day. Problems come back as a result the model can read, never as an exception."""
    try:
        if not _ISO_DATE.fullmatch(day):
            raise ValueError
        date.fromisoformat(day)
    except ValueError:
        return {"error": f"invalid date {day!r}, expected YYYY-MM-DD"}

    try:
        with urllib.request.urlopen(day_url(data_base_url, day), timeout=TIMEOUT_SECONDS) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            # The data service answers 404 when it has no data for a day. That is not a free day.
            return {
                "date": day,
                "data_available": False,
                "message": "The calendar has no data for this day, so it is unknown what is scheduled.",
            }
        return {"date": day, "error": f"calendar service returned HTTP {err.code}"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
        return {"date": day, "error": f"calendar service unreachable: {err}"}


def run(arguments: str, data_base_url: str) -> dict:
    """Execute a tool call whose arguments arrive as a JSON string from the model."""
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"error": f"arguments are not valid JSON: {arguments!r}"}
    if not isinstance(args, dict) or not isinstance(args.get("date"), str):
        return {"error": "parameter 'date' (string, YYYY-MM-DD) is required"}
    return get_calendar_day(data_base_url, args["date"].strip())
