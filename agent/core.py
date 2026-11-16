"""The agent loop: the model takes steps until it answers in text or the step limit is reached.

Every step is one model call. If the model asks for tools, they run and their results go back into
the history for the next step. A step that goes wrong is logged and the next step tries again, so a
single bad step does not abort the run; only the step limit or an error that a retry cannot fix
(wrong key, unknown model) ends a run without an answer.
"""

import json
import time
from datetime import date

import openai
from openai import OpenAI

from . import calendar_tool
from .config import Config
from .run_log import RunLog

REQUEST_TIMEOUT_SECONDS = 60
# Pause before the next step when a step failed on the endpoint's side (rate limit, server or
# network error). The openai client has already retried with backoff at that point.
STEP_RETRY_DELAY_SECONDS = 5

SYSTEM_PROMPT = """\
You are a calendar assistant. Today is {today}.
Look up the appointments with the tool {tool} before you answer; never invent or guess appointments.
Convert every date in the question to YYYY-MM-DD for the tool, and resolve relative dates such as \
"tomorrow" against today. For a question about several days, look up every one of them.
If a tool result contains an error, correct the arguments and try again when that can help; \
otherwise say which day could not be read.
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
    """The run ended without an answer."""


class StepLimitError(AgentError):
    """The model did not answer within the step limit."""


def answer(question: str, config: Config, log: RunLog) -> str:
    """Answer one question about the calendar and return the model's text answer.

    Raises StepLimitError if there is no answer after config.max_steps steps, and lets errors
    through that another step cannot fix.
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
    tool_used = False

    for step in range(1, config.max_steps + 1):
        # Until a tool has run, the model must call one: the answer has to rest on calendar data.
        tool_choice = "auto" if tool_used else "required"
        started = time.perf_counter()
        try:
            message = _model_step(client, config, messages, tool_choice)
        except openai.APIError as err:
            if not _is_recoverable(err):
                raise
            _log_failed_step(log, step, started, type(err).__name__, str(err))
            if step < config.max_steps and not isinstance(err, openai.BadRequestError):
                time.sleep(STEP_RETRY_DELAY_SECONDS)
            continue
        model_ms = _elapsed_ms(started)
        tool_calls = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in message.tool_calls or []
        ]

        if not tool_calls:
            answer_text = (message.content or "").strip()
            if not answer_text:
                _log_failed_step(
                    log, step, started, "EmptyAnswer", "the model returned neither text nor a tool call"
                )
                continue
            log.write("final", ok=True, duration_ms=model_ms, step=step, answer=answer_text)
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
                step=step,
                tool_call_id=call["id"],
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(_run_tool(call, step, config, log), ensure_ascii=False),
                }
            )
        tool_used = True

    raise StepLimitError(f"step limit reached: no answer after {config.max_steps} steps")


def _model_step(client: OpenAI, config: Config, messages: list, tool_choice: str):
    """One step: a model call with the whole history so far. Returns the model's message."""
    try:
        response = _complete(client, config, messages, tool_choice)
    except openai.BadRequestError as err:
        # Groq rejects "required" when the model answers in text instead, e.g. for a request
        # the read-only tool cannot serve. Ask again within the same step without forcing a tool.
        if tool_choice != "required" or err.code != "tool_use_failed":
            raise
        response = _complete(client, config, messages, "auto")
    return response.choices[0].message


def _complete(client: OpenAI, config: Config, messages: list, tool_choice: str):
    """One model call with the whole history so far and the calendar tool on offer."""
    return client.chat.completions.create(
        model=config.model,
        messages=messages,
        tools=[calendar_tool.DEFINITION],
        tool_choice=tool_choice,
    )


def _is_recoverable(err: openai.APIError) -> bool:
    """Whether another step can succeed where this one failed.

    Rate limits, server and network errors pass, and so does a tool call that Groq rejected as
    malformed (tool_use_failed): the model may well get it right the next time. A wrong key, an
    unknown model or any other rejected request would fail again in every step.
    """
    if isinstance(err, (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError)):
        return True
    return isinstance(err, openai.BadRequestError) and err.code == "tool_use_failed"


def _log_failed_step(log: RunLog, step: int, started: float, error_type: str, error: str) -> None:
    # fatal=False: the run goes on with the next step. The error that ends a run is logged by cli.
    log.write(
        "error",
        ok=False,
        duration_ms=_elapsed_ms(started),
        step=step,
        fatal=False,
        error_type=error_type,
        error=error,
    )


def _run_tool(call: dict, step: int, config: Config, log: RunLog) -> dict:
    """Execute one tool call of the model, log it, and return the result for the model.

    Failures come back as a result with "error", so the model can react instead of the run crashing.
    """
    name = call["function"]["name"]
    arguments = call["function"]["arguments"]
    started = time.perf_counter()
    try:
        if name == calendar_tool.NAME:
            result = calendar_tool.run(arguments, config.data_base_url)
        else:
            result = {"error": f"unknown tool {name!r}"}
    except Exception as err:
        # Even a bug in a tool must not end the run; the model sees the error and can go on.
        result = {"error": f"tool {name!r} failed: {type(err).__name__}: {err}"}
    log.write(
        "tool_result",
        # A day without data (HTTP 404) is a valid result; only an "error" result failed.
        ok="error" not in result,
        duration_ms=_elapsed_ms(started),
        tool=name,
        args=_parse_args(arguments),
        step=step,
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
