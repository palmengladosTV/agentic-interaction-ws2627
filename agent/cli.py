"""One complete agent run: log file, answer on stdout, errors on stderr, exit code."""

import sys
import time
from pathlib import Path

from . import core
from .config import REPO_ROOT, load_config
from .run_log import RunLog

LOG_DIR = REPO_ROOT / "logs"
USAGE = 'usage: python -m agent "<question about the calendar>"'


class UsageError(ValueError):
    pass


def run(question: str) -> tuple[int, Path]:
    """Answer one question. Returns the exit code and the path of the run's log file.

    The last line of every log says how the run ended: "final" (exit code 0) or "error" with
    fatal true and the exit code.
    """
    # Answers may contain characters the Windows console code page cannot encode.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    question = question.strip()
    started = time.perf_counter()
    exit_code = 1

    with RunLog(LOG_DIR) as log:
        try:
            if not question:
                exit_code = 2
                raise UsageError(USAGE)
            config = load_config()
            log.model = config.model
            log.write(
                "user_task",
                ok=True,
                duration_ms=0,
                task=question,
                base_url=config.base_url,
                data_base_url=config.data_base_url,
                max_steps=config.max_steps,
            )
            answer = core.answer(question, config, log)
            print(answer, flush=True)
            exit_code = 0
        except KeyboardInterrupt:
            exit_code = 130
            _log_end(log, started, "KeyboardInterrupt", "interrupted by the user", exit_code)
            raise
        except Exception as err:
            _log_end(log, started, type(err).__name__, str(err), exit_code)
            print(f"error: {err}", file=sys.stderr, flush=True)
    return exit_code, log.path


def _log_end(log: RunLog, started: float, error_type: str, error: str, exit_code: int) -> None:
    # The failing step is not always known, so duration_ms is the run time up to the error.
    log.write(
        "error",
        ok=False,
        duration_ms=round((time.perf_counter() - started) * 1000),
        fatal=True,
        error_type=error_type,
        error=error,
        exit_code=exit_code,
    )


def main() -> int:
    try:
        exit_code, _ = run(" ".join(sys.argv[1:]))
    except KeyboardInterrupt:
        return 130
    return exit_code
