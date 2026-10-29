"""Interactive console chat for trying out several questions in a row.

Start it with `python chat.py` (or by double-clicking it): it switches to the project's .venv on
its own. Every question is an independent agent run, exactly like `python -m agent "..."`, and
writes its own log file. The chat keeps no history between questions.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

# Re-start with the virtual environment's interpreter, so the packages from requirements.txt are
# available even when .venv was not activated.
if VENV_PYTHON.exists() and Path(sys.prefix).resolve() != VENV.resolve():
    try:
        sys.exit(subprocess.call([str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]]))
    except KeyboardInterrupt:
        sys.exit(0)

from agent.cli import run  # noqa: E402  (import only after the interpreter is settled)

EXIT_COMMANDS = {"exit", "quit", "q"}


def main() -> int:
    print("Calendar agent - interactive test")
    print("Every question is a separate run with its own log in logs/. Type 'exit' to quit.")
    try:
        while True:
            question = input("\nYou: ").strip()
            if not question:
                continue
            if question.lower() in EXIT_COMMANDS:
                return 0

            print("Agent: ", end="", flush=True)
            exit_code, log_path = run(question)
            status = "" if exit_code == 0 else f"exit code {exit_code}, "
            print(f"({status}log: {log_path.relative_to(ROOT)})")
    except (EOFError, KeyboardInterrupt):
        # Ctrl+D / Ctrl+Z or Ctrl+C ends the chat.
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
