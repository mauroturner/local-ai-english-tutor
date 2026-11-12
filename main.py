"""Entry point: start the AI English tutor from the repository root.

Usage (with the virtual environment active and Ollama running):

    python main.py

Works without installing the package: ``src/`` is added to the import path.
Installing it (``pip install -e .``) also provides the ``english-tutor`` command.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import english_tutor.__main__ as _app  # noqa: E402  (needs src/ on the path)
from english_tutor.__main__ import main  # noqa: E402  re-exported for callers

__all__ = ["main", "run"]


def run() -> int:
    """Start the application and return its exit code."""
    return _app.main()


if __name__ == "__main__":
    sys.exit(run())
