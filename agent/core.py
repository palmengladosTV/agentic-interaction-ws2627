"""The agent loop: model -> tool -> model, until the model answers in text."""

import json
import time
from datetime import date

from openai import BadRequestError, OpenAI

from . import calendar_tool
from .config import Config
from .run_log import RunLog

# Upper bound on model calls per question. Without it, a model that keeps calling the tool would
# loop forever, and every round resends the whole history (tokens, rate limit, time).
# One tool round is the normal case; a few more allow questions that span several days.
MAX_TURNS = 10
REQUEST_TIMEOUT_SECONDS = 60

SYSTEM_PROMPT = """\
You are a calendar assistant. Today is {today}.
Look up the appointments with the tool {tool} before you answer; never invent or guess appointments.
Convert every date in the question to YYYY-MM-DD for the tool, and resolve relative dates such as \
"tomorrow" against today.
You can only read appointments, not create, change or delete them. If someone asks for that, say \
so briefly instead of calling the tool.
Answer in the same language as the question: an English question gets an English answer, a German \
question a German one. Keep it short and use plain text without Markdown, because the answer is \
printed in a terminal.
For each appointment give start and end time (or "all day"), title and location; leave out an \
empty location.
An empty event list means the day is free. A result with data_available false means the calendar \
has no data for that day: say that, and do not call the day free.\
"""


class AgentError(RuntimeError):
    """The model gave no usable answer (empty text, or no text within MAX_TURNS)."""


def _tool_choice(turn: int) -> str:
    """How free the model is in this turn: must call the tool, may call it, or must answer."""
    if turn == 1:
        return "required"  # the answer must be grounded in the calendar
    if turn == MAX_TURNS:
        return "none"  # last turn: force a text answer
    return "auto"


def answer(question: str, config: Config, log: RunLog) -> str:
    """Answer one question about the calendar and return the model's text answer.

    Each turn is one model call. If the model asks for tools, they are run and their results are
    appended to the history for the next turn; the first turn without tool calls is the answer.
    """
    client = OpenAI(
        base_url=config.base_url, api_key=config.api_key, timeout=REQUEST_TIMEOUT_SECONDS
    )
    today = date.today()
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                today=f"{today:%A}, {today.isoformat()}", tool=calendar_tool.NAME
            ),
        },
        {"role": "user", "content": question},
    ]

    for turn in range(1, MAX_TURNS + 1):
        choice = _tool_choice(turn)
        started = time.perf_counter()
        try:
            response = _complete(client, config, messages, choice)
        except BadRequestError as err:
            # Groq rejects "required" when the model answers in text instead, e.g. for a request
            # the read-only tool cannot serve. Ask again without forcing a tool call.
            if choice != "required" or err.code != "tool_use_failed":
                raise
            response = _complete(client, config, messages, "auto")
        model_ms = _elapsed_ms(started)
        message = response.choices[0].message
        tool_calls = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in message.tool_calls or []
        ]

        if not tool_calls:
            if not message.content or not message.content.strip():
                raise AgentError("the model returned an empty answer")
            answer_text = message.content.strip()
            log.write("final", ok=True, duration_ms=model_ms, turn=turn, answer=answer_text)
            return answer_text

        messages.append({"role": "assistant", "content": message.content or "", "tool_calls": tool_calls})
        for call in tool_calls:
            # duration_ms of a tool_call is the model call in which the model chose this tool.
            log.write(
                "tool_call",
                ok=True,
                duration_ms=model_ms,
                tool=call["function"]["name"],
                args=_parse_args(call["function"]["arguments"]),
                turn=turn,
                tool_call_id=call["id"],
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(_run_tool(call, turn, config, log), ensure_ascii=False),
                }
            )

    raise AgentError(f"no answer after {MAX_TURNS} model calls")


def _complete(client: OpenAI, config: Config, messages: list, tool_choice: str):
    """One model call with the whole history so far and the calendar tool on offer."""
    return client.chat.completions.create(
        model=config.model,
        messages=messages,
        tools=[calendar_tool.DEFINITION],
        tool_choice=tool_choice,
    )


def _run_tool(call: dict, turn: int, config: Config, log: RunLog) -> dict:
    """Execute one tool call of the model, log it, and return the result for the model.

    Failures come back as a result with "error", so the model can react instead of the run crashing.
    """
    name = call["function"]["name"]
    arguments = call["function"]["arguments"]
    started = time.perf_counter()
    if name == calendar_tool.NAME:
        result = calendar_tool.run(arguments, config.data_base_url)
    else:
        result = {"error": f"unknown tool {name!r}"}
    log.write(
        "tool_result",
        # A day without data (HTTP 404) is a valid result; only an "error" result failed.
        ok="error" not in result,
        duration_ms=_elapsed_ms(started),
        tool=name,
        args=_parse_args(arguments),
        turn=turn,
        tool_call_id=call["id"],
        result=result,
    )
    return result


def _parse_args(arguments: str) -> object:
    """Log arguments as JSON when the model sent valid JSON, otherwise as the raw string."""
    try:
        return json.loads(arguments)
    except (TypeError, json.JSONDecodeError):
        return arguments


def _elapsed_ms(started: float) -> int:
    """Milliseconds since started, a time.perf_counter() value."""
    return round((time.perf_counter() - started) * 1000)
