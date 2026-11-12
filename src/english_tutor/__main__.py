"""Composition root: builds adapters, the session and the window."""

from __future__ import annotations

import logging
import os
import sys

from .adapters.file_conversation_log import FileConversationLog
from .adapters.folders import open_folder
from .adapters.json_mistake_store import JsonMistakeStore
from .adapters.json_settings_store import JsonSettingsStore
from .adapters.keyboard_ptt import KeyboardPushToTalk
from .adapters.ollama_chat import OllamaTutorModel
from .adapters.piper_tts import NullSynthesizer, PiperSynthesizer
from .adapters.sounddevice_recorder import SoundDeviceRecorder
from .adapters.whisper_stt import WhisperTranscriber
from .application.events import ErrorRaised, LevelChanged, SessionEvent
from .application.preferences import SettingsService
from .application.ptt_gate import PttGate
from .application.session import ConversationSession
from .audio.devices import list_input_devices
from .config import (
    AppConfig,
    ConfigError,
    default_project_root,
    load_config,
    resolve_settings_path,
)
from .i18n import set_language
from .logging_setup import configure_logging
from .ports import SpeechSynthesizer
from .restart import finish_restart
from .settings.model import settings_env

logger = logging.getLogger("english_tutor")


def _build_tts(cfg: AppConfig) -> tuple[SpeechSynthesizer, str | None]:
    """Return the synthesizer and a warning message if voice output is off."""
    if not cfg.tts_enabled:
        return NullSynthesizer(), "Voice output disabled (TUTOR_TTS=0)."
    piper = PiperSynthesizer(cfg.piper_exe, cfg.piper_voice)
    if piper.available:
        return piper, None
    where = cfg.piper_exe if cfg.piper_exe is not None else "piper/piper.exe not found"
    return NullSynthesizer(), f"Text-only (Piper not found or voice files missing: {where})"


def _apply_log_level(level: str) -> None:
    """Change the log level of the running app (a live setting)."""
    logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))


def main() -> int:
    """Start the application; returns a process exit code."""
    root = default_project_root()
    settings_service = SettingsService(
        JsonSettingsStore(resolve_settings_path(os.environ, root)), None, os.environ
    )
    loaded = settings_service.load()
    try:
        cfg = load_config(overrides=settings_env(loaded.settings))
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    configure_logging(cfg.log_level, cfg.data_dir / "logs")
    set_language(loaded.settings.language)
    # Imported here so configuration errors are reported without loading Tk.
    from .ui import theme
    from .ui.app_window import TutorWindow
    from .ui.services import UiPaths, UiServices
    from .ui.settings.window import SettingsWindow

    devices, default_device = list_input_devices()
    tts, tts_warning = _build_tts(cfg)
    if tts_warning:
        logger.warning(tts_warning)

    logger.info("Local data folder: %s", cfg.data_dir)
    window_ref: list[TutorWindow] = []

    def emit(event: SessionEvent) -> None:
        if window_ref:
            window_ref[0].post(event)

    recorder = SoundDeviceRecorder(on_level=lambda value: emit(LevelChanged(value)))
    tutor = OllamaTutorModel(
        cfg.ollama_url, cfg.ollama_model, cfg.ollama_timeout_s, cfg.llm_temperature
    )
    session = ConversationSession(
        WhisperTranscriber(cfg),
        tutor,
        tts,
        recorder,
        emit,
        history_exchanges=cfg.history_exchanges,
        ptt_label=cfg.ptt_label,
        conversation_log=FileConversationLog(cfg.data_dir / "conversations"),
        mistakes=JsonMistakeStore(cfg.data_dir / "mistakes.json"),
        coach=tutor,
    )
    gate = PttGate(session.on_ptt_press, session.on_ptt_release)
    theme.apply_appearance(loaded.settings.appearance_mode, loaded.settings.ui_scale)
    services = UiServices(
        settings_service,
        UiPaths(cfg.data_dir, cfg.data_dir / "logs"),
        open_folder,
        apply_log_level=_apply_log_level,
        on_applied=lambda saved: window_ref[0].apply_settings(saved),
        on_restart_needed=lambda keys: window_ref[0].show_restart_banner(keys),
        ptt_gate=gate,
    )
    window = TutorWindow(
        cfg,
        session,
        devices,
        default_device,
        loaded.settings,
        on_open_settings=lambda: SettingsWindow.open(window_ref[0], services),
    )
    window_ref.append(window)
    for warning in loaded.warnings:
        window.post(ErrorRaised(warning))

    ptt = KeyboardPushToTalk(cfg.ptt_key)
    try:
        ptt.start(gate.press, gate.release)
    except Exception as exc:  # the keyboard hook needs OS privileges on some systems
        logger.exception("Push-to-talk unavailable")
        window.post(ErrorRaised(f"PTT unavailable: {exc}"))

    session.start()
    exit_code = 0
    try:
        window.mainloop()
    finally:
        ptt.stop()
        session.shutdown()
        if window.restart_requested:
            exit_code = finish_restart()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
