"""Checking the arguments the model passes to a tool."""

import re
from datetime import date

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class ToolInputError(ValueError):
    """The model passed arguments the tool cannot use. The message goes back to the model."""


def text(args: dict, name: str) -> str:
    value = args.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"parameter {name!r} (string) is required")
    return value.strip()


def day(args: dict, name: str = "date") -> str:
    value = text(args, name)
    try:
        if not _ISO_DATE.fullmatch(value):
            raise ValueError
        date.fromisoformat(value)
    except ValueError:
        raise ToolInputError(f"invalid date {value!r}, expected YYYY-MM-DD") from None
    return value
