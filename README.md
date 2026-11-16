# agentic-interaction-ws2627
Exercise for course Agentic Human-AI Interaction at Ulm University

## Exercise 1: First tool call

A command line agent that answers questions about the mock calendar. The model calls a tool,
the tool reads the appointments of one day from the data service, and the model answers with
that result (model → tool → model).

### Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then put your API key into .env
```

### Configuration

The agent reads `.env` at start-up. Variables that are already set in the environment take
precedence over `.env`. `.env` is git-ignored and must never be committed.

| Variable | Example |
|---|---|
| `OPENAI_BASE_URL` | `https://api.groq.com/openai/v1` |
| `MODEL` | `openai/gpt-oss-20b` |
| `OPENAI_API_KEY` | your key |
| `DATA_BASE_URL` | `https://jhbelz.github.io/agentic-interaction-data/v1` |
| `MAX_STEPS` | optional, maximum steps (model calls) per run, default `10` |

The agent uses the `openai` library against any OpenAI-compatible endpoint, so Groq is only the
default, not a requirement.

### Usage

```bash
python -m agent "Was steht am 29.10.2026 im Kalender?"
```

The answer goes to standard output and the exit code is 0. Errors go to standard error with
exit code 1 (exit code 2 if no question was given, 130 if interrupted with Ctrl+C).

To try several questions in a row, start the interactive chat. It switches to `.venv` on its own;
every question is a separate run with its own log, and `exit` quits:

```bash
python chat.py
```

### How it works

- `agent/calendar_tool.py`: the tool `get_calendar_day(date)`. Its name, purpose and parameter
  are passed to the model as a description. It fetches `{DATA_BASE_URL}/calendar/{YYYY-MM-DD}.json`.
  A 404 from the data service ("no data") and other failures are returned to the model as a
  result instead of crashing the agent.
- `agent/core.py`: the agent loop (see exercise 3 below). Until a tool has run, the model must
  call one, so every answer is grounded in the calendar. The tool results go back to the model,
  which then answers or takes further steps.
- `agent/config.py`: loads `.env` and the environment.
- `agent/run_log.py`: the per-run JSONL log.
- `agent/cli.py`: one complete run (log, answer on stdout, errors, exit code).
- `agent/__main__.py`: the command line entry point.
- `chat.py`: the interactive console chat.

### Logs

Every run writes its own file `logs/run-<YYYYMMDD-HHMMSS>-<run_id>.jsonl` inside the repository
folder (git-ignored). Each line is one JSON object. Every line has all fields of the run log
specification; a field that does not apply to an event is `null`.

| Field | Content |
|---|---|
| `ts` | time stamp, ISO 8601 with time zone |
| `run_id` | one ID per run |
| `event` | `user_task`, `tool_call`, `tool_result`, `final` or `error` |
| `tool`, `args` | tool name and arguments (for `tool_call` and `tool_result`) |
| `ok` | whether the step succeeded |
| `model` | model name as sent to the endpoint |
| `duration_ms` | duration of the step |

What the events mean and which extra fields they carry:

| `event` | step | `duration_ms` | extra fields |
|---|---|---|---|
| `user_task` | the question from the command line | `0` | `task`, `base_url`, `data_base_url`, `max_steps` |
| `tool_call` | the model asks for a tool | the model call | `step`, `tool_call_id` |
| `tool_result` | the tool ran; `ok` is `false` if it returned an error (a day without data, HTTP 404, is a valid result) | the tool execution | `step`, `tool_call_id`, `result` |
| `final` | the model answers; the run ends with exit code 0 | the model call | `step`, `answer` |
| `error` with `fatal: false` | one step failed, the next step tries again | the failed model call | `step`, `error_type`, `error` |
| `error` with `fatal: true` | the run ends without an answer (exit code ≠ 0) | the run up to the error | `error_type`, `error`, `exit_code` |

The last line of every log says how the run ended: `final` or `error` with `fatal: true`. The API
key is never logged.

## Exercise 3: The agent loop

`python -m agent "..."` runs as many steps as the task needs. **Every step is one model call.** If
the model asks for tools, they run and their results go back into the history for the next step;
the first step in which the model answers in text ends the run. A question about two days takes
two tool calls, either in one step or one after the other:

```bash
python -m agent "What is on 29 Oct 2026 and on 30 Oct 2026?"
```

### A visible end

No run can go on forever. Each run has at most `MAX_STEPS` steps (default 10), each model call
times out after 60 seconds and each data request after 15 seconds. A run ends in exactly one of
these ways, which the exit code and the last log line both show:

| End | Exit code | Last log line |
|---|---|---|
| the model answered | `0` | `final` |
| step limit reached without an answer | `1` | `error`, `fatal: true`, `error_type: "StepLimitError"` |
| an error that another step cannot fix (wrong key, unknown model, missing configuration) | `1` | `error`, `fatal: true` |
| no question given | `2` | `error`, `fatal: true`, `error_type: "UsageError"` |
| interrupted with Ctrl+C | `130` | `error`, `fatal: true`, `error_type: "KeyboardInterrupt"` |

Reaching the step limit is an error, never a success: the last step is not turned into a forced
answer.

### Errors along the way

A single step that goes wrong does not abort the run:

- **A tool fails** (invalid date, data service unreachable, even an exception inside the tool):
  the error goes back to the model as the tool's result (`tool_result` with `ok: false`), and the
  model can correct the arguments or report which day could not be read.
- **A model call fails** with a rate limit (429), a server error (5xx), a lost connection, or a
  tool call that Groq rejected as malformed (`tool_use_failed`): the step is logged as `error` with
  `fatal: false` and the next step tries again. The `openai` client itself has already retried
  with backoff; for rate limits and server errors the agent waits another 5 seconds.
- **The model returns neither text nor a tool call**: logged as `EmptyAnswer` (`fatal: false`),
  and the next step tries again.

Failed steps count towards the step limit, so even an endpoint that keeps failing ends the run.

### Tests

Offline tests replace the model and the data service with scripted fakes and run the whole agent
(configuration, loop, tools, log file). They use no tokens:

```bash
python -m unittest -v
```

They cover single- and multi-day questions, the step limit, unrecoverable errors, and every kind of
error along the way listed above.

### Own multi-step tests

Real runs against Groq (`openai/gpt-oss-20b`) on 16 Nov 2026, checked in each run's log. Sequence
of events, numbers are steps:

| Task | Setting | Exit | What the log shows |
|---|---|---|---|
| "What is on 29 Oct 2026 and on 30 Oct 2026?" | | 0 | 1: tool 29 Oct (3 events), 2: tool 30 Oct (0 events), 3: `final`, both days answered |
| "Was steht am 29.10.2026 im Kalender?" (exercise 1) | | 0 | 1: tool 29 Oct, 2: `final` |
| "Was steht von Montag, 2.11.2026, bis Mittwoch, 4.11.2026, an?" | | 0 | three tool steps for 2, 3 and 4 Nov, 4: `final` |
| "What is on 29 Oct 2026 and on 24 Dec 2026?" | | 0 | 24 Dec is HTTP 404: `tool_result` with `data_available: false`, the answer says there is no data |
| "Was steht am 31.11.2026 und am 03.11.2026 an?" | | 0 | the model saw that 31 Nov does not exist, looked up only 3 Nov and said so |
| "Was steht am 29.10.2026 im Kalender?" | `DATA_BASE_URL=http://127.0.0.1:9/v1` | 0 | `tool_result` with `ok: false` (connection refused), the run went on and the answer says the calendar could not be reached |
| "What is on 29 Oct 2026 and on 30 Oct 2026?" | `MAX_STEPS=1` | 1 | 1: tool 29 Oct, then `error` with `fatal: true`, `StepLimitError`; nothing on stdout |
| "Was steht am 29.10.2026 im Kalender?" | `OPENAI_BASE_URL=http://127.0.0.1:9/v1`, `MAX_STEPS=2` | 1 | 1 and 2: `error` with `fatal: false`, `APIConnectionError`; then `error` with `fatal: true`, `StepLimitError` |
