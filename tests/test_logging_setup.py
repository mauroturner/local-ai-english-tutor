"""configure_logging: rotating app.log created lazily, console only with a stderr."""

from __future__ import annotations

import logging
import logging.handlers
import sys

import pytest

from english_tutor.logging_setup import configure_logging


@pytest.fixture(autouse=True)
def restore_root_logger():
    root = logging.getLogger()
    level, handlers = root.level, list(root.handlers)
    yield
    for handler in list(root.handlers):
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)


def file_handlers(handlers):
    return [h for h in handlers if isinstance(h, logging.handlers.RotatingFileHandler)]


def test_file_handler_is_lazy_and_has_the_rotation_settings(tmp_path):
    logs = tmp_path / "data" / "logs"
    handlers = configure_logging("INFO", logs)
    (handler,) = file_handlers(handlers)
    assert (handler.maxBytes, handler.backupCount) == (1_000_000, 3)
    assert handler.encoding == "utf-8"
    assert handler.delay is True
    assert not (logs / "app.log").exists()
    logging.getLogger("english_tutor.test").info("hello ñ")
    handler.flush()
    assert "hello ñ" in (logs / "app.log").read_text(encoding="utf-8")


def test_level_is_applied_and_unknown_names_fall_back_to_info(tmp_path):
    configure_logging("DEBUG", tmp_path / "logs")
    assert logging.getLogger().level == logging.DEBUG
    configure_logging("NOPE", tmp_path / "logs")
    assert logging.getLogger().level == logging.INFO


def test_console_handler_follows_stderr(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    handlers = configure_logging("INFO", tmp_path / "logs")
    assert len(handlers) == 1
    assert file_handlers(handlers)
    monkeypatch.undo()
    with_console = configure_logging("INFO", tmp_path / "logs")
    streams = [h for h in with_console if type(h) is logging.StreamHandler]
    assert len(streams) == 1


def test_reconfiguring_does_not_stack_handlers(tmp_path):
    configure_logging("INFO", tmp_path / "logs")
    configure_logging("INFO", tmp_path / "logs")
    root = logging.getLogger()
    assert len(file_handlers(root.handlers)) == 1


def test_unwritable_logs_folder_still_gives_a_console_handler(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a folder", encoding="utf-8")
    handlers = configure_logging("INFO", blocker / "logs")
    assert not file_handlers(handlers)
