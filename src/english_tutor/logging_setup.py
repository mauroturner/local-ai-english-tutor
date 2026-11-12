"""Application logging: a rotating file under the data folder plus the console."""

from __future__ import annotations

import logging
import logging.handlers
import sys
import tempfile
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3
_OWN = "_english_tutor_handler"


def _file_handler(logs_dir: Path) -> logging.Handler:
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logging.handlers.RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )


def configure_logging(
    level: str, logs_dir: Path, fallback_dir: Path | None = None
) -> tuple[logging.Handler, ...]:
    """Send log records to ``<logs_dir>/app.log`` and, when there is one, the console.

    The file rotates at 1 MB and keeps 3 backups; it is created on the first
    record. The console handler is skipped when ``sys.stderr`` is ``None``
    (a windowed ``pythonw`` run). If ``logs_dir`` cannot be created, the log goes
    to ``fallback_dir`` (default: ``<temp>/english_tutor/logs``) and the failure is
    logged once the handlers are attached, so it is never lost silently. Calling
    this again replaces the handlers added by the previous call. Returns the
    handlers it installed.
    """
    root = logging.getLogger()
    for old in [h for h in root.handlers if getattr(h, _OWN, False)]:
        root.removeHandler(old)
        old.close()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter(_FORMAT)
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    problem: OSError | None = None
    try:
        handlers.append(_file_handler(logs_dir))
    except OSError as exc:
        problem = exc
        fallback = fallback_dir or Path(tempfile.gettempdir()) / "english_tutor" / "logs"
        try:
            handlers.append(_file_handler(fallback))
        except OSError:
            pass  # nothing writable left; the console (if any) still works
    for handler in handlers:
        handler.setFormatter(formatter)
        setattr(handler, _OWN, True)
        root.addHandler(handler)
    if problem is not None:  # after attaching, so the warning reaches a handler
        logging.getLogger(__name__).warning("Log file unavailable (%s): %s", logs_dir, problem)
    return tuple(handlers)
