"""Per-run JSONL log: every run gets its own file, one JSON object per line.

Every line carries the fields of the run log specification: ts, run_id, event, tool, args, ok,
model and duration_ms. Fields that do not apply to an event are null.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

EVENTS = ("user_task", "tool_call", "tool_result", "final", "error")


def _now() -> datetime:
    return datetime.now().astimezone()


class RunLog:
    def __init__(self, directory: Path):
        self.run_id = uuid.uuid4().hex[:12]
        self.model: str | None = None  # set once the configuration is loaded
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"run-{_now():%Y%m%d-%H%M%S}-{self.run_id}.jsonl"
        self._file = self.path.open("w", encoding="utf-8")

    def write(
        self,
        event: str,
        *,
        ok: bool,
        duration_ms: int | None = None,
        tool: str | None = None,
        args: object = None,
        **details,
    ) -> None:
        if event not in EVENTS:
            raise ValueError(f"unknown log event {event!r}")
        record = {
            "ts": _now().isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "event": event,
            "tool": tool,
            "args": args,
            "ok": ok,
            "model": self.model,
            "duration_ms": duration_ms,
            **details,
        }
        self._file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        # Flush per line so the log survives a crash mid-run.
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "RunLog":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
