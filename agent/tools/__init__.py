"""The tools the model can call. Each one reads one kind of mock data via DATA_BASE_URL.

Every tool module has NAME, definition(data) for the model, and run(arguments, data) that returns
the result as a dict. Problems with the arguments or the data come back as results, never raised.
"""

import json

from ..data_service import DataService
from . import calendar_day, connections, weather
from .args import ToolInputError

_TOOLS = {module.NAME: module for module in (calendar_day, weather, connections)}


def definitions(data: DataService) -> list[dict]:
    """Name, purpose and parameters of every tool as the model gets them."""
    return [module.definition(data) for module in _TOOLS.values()]


def run(name: str, arguments: str, data: DataService) -> dict:
    """Execute one tool call whose arguments arrive as a JSON string from the model."""
    module = _TOOLS.get(name)
    if module is None:
        return {"error": f"unknown tool {name!r}, available: {', '.join(_TOOLS)}"}
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"error": f"arguments are not valid JSON: {arguments!r}"}
    if not isinstance(parsed, dict):
        return {"error": "arguments must be a JSON object"}
    try:
        return module.run(parsed, data)
    except ToolInputError as err:
        return {"error": str(err)}
