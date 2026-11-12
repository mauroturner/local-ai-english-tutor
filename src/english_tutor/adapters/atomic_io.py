"""Crash-safe text file writes."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` so the old file survives any failure.

    The text goes to ``<name>.tmp`` in the same folder, is flushed to disk and is
    swapped in with ``os.replace``. Parent folders are created. Raises OSError.
    """
    tmp = path.with_name(f"{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            logger.debug("Could not remove %s", tmp)
        raise
