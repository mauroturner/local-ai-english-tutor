"""Application logging: a rotating file under the data folder plus the console."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3
_OWN = "_english_tutor_handler"


def configure_logging(level: str, logs_dir: Path) -> tuple[logging.Handler, ...]:
    """Send log records to ``<logs_dir>/app.log`` and, when there is one, the console.

    The file rotates at 1 MB and keeps 3 backups; it is created on the first
    record. The console handler is skipped when ``sys.stderr`` is ``None``
    (a windowed ``pythonw`` run). Calling this again replaces the handlers added
    by the previous call. Returns the handlers it installed.
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
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                logs_dir / "app.log",
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
                delay=True,
            )
        )
    except OSError as exc:
        logging.getLogger(__name__).warning("Log file unavailable (%s): %s", logs_dir, exc)
    for handler in handlers:
        handler.setFormatter(formatter)
        setattr(handler, _OWN, True)
        root.addHandler(handler)
    return tuple(handlers)
