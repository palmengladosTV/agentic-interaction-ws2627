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

The agent uses the `openai` library against any OpenAI-compatible endpoint, so Groq is only the
default, not a requirement.

### Usage

```bash
python -m agent "Was steht am 29.10.2026 im Kalender?"
```

The answer goes to standard output and the exit code is 0. Errors go to standard error with
exit code 1 (exit code 2 if no question was given).

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
- `agent/core.py`: the agent loop. The first model call must use the tool, so every answer is
  grounded in the calendar. The tool results go back to the model, which then answers. A question
  about several days may take more than one tool round (at most 5 model calls).
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
| `user_task` | the question from the command line | `0` | `task`, `base_url`, `data_base_url` |
| `tool_call` | the model asks for a tool | the model call | `turn`, `tool_call_id` |
| `tool_result` | the tool ran; `ok` is `false` if it returned an error (a day without data, HTTP 404, is a valid result) | the tool execution | `turn`, `tool_call_id`, `result` |
| `final` | the model answers | the model call | `turn`, `answer` |
| `error` | the run failed (exit code ≠ 0) | the run up to the error | `error_type`, `error`, `exit_code` |

The API key is never logged.
