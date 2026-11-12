"""Relaunching the app after a setting that needs a restart."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MODULE = "english_tutor"


def restart_command(orig_argv: Sequence[str], executable: str) -> list[str]:
    """The command that starts this app again.

    ``orig_argv`` is ``sys.orig_argv`` (interpreter first). A script run
    (``python main.py ...``) or ``python -m english_tutor`` is repeated as it was;
    anything else (the ``english-tutor`` launcher, ``-c``, another module) becomes
    ``python -m english_tutor``.
    """
    args = list(orig_argv[1:])
    if args and args[0].lower().endswith(".py"):
        return [executable, *args]
    if len(args) >= 2 and args[0] == "-m" and args[1].split(".")[0] == _MODULE:
        return [executable, *args]
    return [executable, "-m", _MODULE]


def windowless_executable(executable: str) -> str:
    """``pythonw.exe`` next to ``python.exe`` when it exists, else ``executable``."""
    path = Path(executable)
    if path.name.lower() == "python.exe":
        candidate = path.with_name("pythonw.exe")
        if candidate.is_file():
            return str(candidate)
    return executable


def spawn_restart(
    orig_argv: Sequence[str] | None = None,
    executable: str | None = None,
    popen: Callable[..., Any] = subprocess.Popen,
) -> bool:
    """Start the new process detached from this one; False (and a log entry) on failure."""
    command = restart_command(
        sys.orig_argv if orig_argv is None else orig_argv,
        sys.executable if executable is None else executable,
    )
    command[0] = windowless_executable(command[0])
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if os.path.basename(command[0]).lower() != "pythonw.exe":
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    try:
        popen(command, creationflags=flags, close_fds=True)
    except OSError:
        logger.exception("Could not restart the application: %s", command)
        return False
    logger.info("Restarting: %s", command)
    return True
