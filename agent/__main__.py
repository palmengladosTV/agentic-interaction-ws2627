"""Command line entry point: python -m agent "Was steht am 29.10.2026 im Kalender?"."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
