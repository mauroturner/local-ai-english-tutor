"""Composition root: builds adapters, the session and the window."""

from __future__ import annotations

import logging
import sys

from .adapters.keyboard_ptt import KeyboardPushToTalk
from .adapters.ollama_chat import OllamaTutorModel
from .adapters.piper_tts import NullSynthesizer, PiperSynthesizer
from .adapters.sounddevice_recorder import SoundDeviceRecorder
from .adapters.whisper_stt import WhisperTranscriber
from .application.events import ErrorRaised, LevelChanged, SessionEvent
from .application.session import ConversationSession
from .audio.devices import list_input_devices
from .config import AppConfig, ConfigError, load_config
from .ports import SpeechSynthesizer

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


def main() -> int:
    """Start the application; returns a process exit code."""
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Imported here so configuration errors are reported without loading Tk.
    from .ui.app_window import TutorWindow

    devices, default_device = list_input_devices()
    tts, tts_warning = _build_tts(cfg)
    if tts_warning:
        logger.warning(tts_warning)

    window_ref: list[TutorWindow] = []

    def emit(event: SessionEvent) -> None:
        if window_ref:
            window_ref[0].post(event)

    recorder = SoundDeviceRecorder(on_level=lambda value: emit(LevelChanged(value)))
    session = ConversationSession(
        WhisperTranscriber(cfg),
        OllamaTutorModel(
            cfg.ollama_url, cfg.ollama_model, cfg.ollama_timeout_s, cfg.llm_temperature
        ),
        tts,
        recorder,
        emit,
        history_exchanges=cfg.history_exchanges,
        ptt_label=cfg.ptt_label,
    )
    window = TutorWindow(cfg, session, devices, default_device)
    window_ref.append(window)

    ptt = KeyboardPushToTalk(cfg.ptt_key)
    try:
        ptt.start(session.on_ptt_press, session.on_ptt_release)
    except Exception as exc:  # the keyboard hook needs OS privileges on some systems
        logger.exception("Push-to-talk unavailable")
        window.post(ErrorRaised(f"PTT unavailable: {exc}"))

    session.start()
    try:
        window.mainloop()
    finally:
        ptt.stop()
        session.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
