"""Conversation session: the state machine behind every learner turn."""

from __future__ import annotations

import logging
import threading
from typing import Callable

from ..audio.processing import prepare_for_stt
from ..domain.corrections import dedupe, filter_corrections, pick_live, spoken_line
from ..domain.models import (
    Correction,
    SessionReport,
    SessionState,
    Severity,
    Turn,
)
from ..ports import (
    AdapterError,
    AudioRecorder,
    LlmUnavailable,
    SpeechSynthesizer,
    SpeechToText,
    TtsError,
    TutorModel,
)
from .events import (
    ErrorRaised,
    EventSink,
    LevelChanged,
    ReportReady,
    StateChanged,
    TutorSaid,
    UserSaid,
)
from .history import ChatHistory
from .worker import Runner, SerialWorker

logger = logging.getLogger(__name__)


class ConversationSession:
    """Coordinates recording, transcription, the tutor model and speech.

    Threading model: ``on_ptt_press`` / ``on_ptt_release`` / ``end_session`` may
    be called from any thread and never block on slow work. All slow work and
    all mutation of ``turns`` and history happen on the runner (one job at a
    time). The state is guarded by a lock.
    """

    def __init__(
        self,
        stt: SpeechToText,
        tutor: TutorModel,
        tts: SpeechSynthesizer,
        recorder: AudioRecorder,
        emit: EventSink,
        *,
        history_exchanges: int = 6,
        runner: Runner | None = None,
        ptt_label: str = "Right Ctrl",
    ) -> None:
        self._stt = stt
        self._tutor = tutor
        self._tts = tts
        self._recorder = recorder
        self._emit = emit
        self._runner: Runner = runner if runner is not None else SerialWorker()
        self._ptt_label = ptt_label
        self._history = ChatHistory(history_exchanges)
        self._turns: list[Turn] = []
        self._state = SessionState.LOADING
        self._lock = threading.Lock()
        self._recorder_lock = threading.Lock()
        self._device_index: int | None = None

    # ------------------------------------------------------------------ state
    @property
    def state(self) -> SessionState:
        """Current state of the session."""
        with self._lock:
            return self._state

    @property
    def turns(self) -> tuple[Turn, ...]:
        """Completed turns of the running session."""
        return tuple(self._turns)

    def _set_state(self, state: SessionState, message: str = "") -> None:
        with self._lock:
            self._state = state
        self._emit(StateChanged(state, message))

    def _transition(
        self, expected: SessionState, new: SessionState, message: str = ""
    ) -> bool:
        """Atomically move from ``expected`` to ``new``; False if not in ``expected``."""
        with self._lock:
            if self._state is not expected:
                return False
            self._state = new
        self._emit(StateChanged(new, message))
        return True

    def _fail(self, message: str) -> None:
        self._emit(ErrorRaised(message))
        self._set_state(SessionState.IDLE, "Ready")

    def _submit(self, job: Callable[[], None]) -> None:
        """Run ``job`` on the worker; an unexpected error always ends in IDLE."""

        def guarded() -> None:
            try:
                job()
            except Exception as exc:  # last-resort guard: never leave the session stuck
                logger.exception("Unexpected error in %s", getattr(job, "__name__", job))
                self._fail(f"Unexpected error: {exc}")

        self._runner.submit(guarded)

    # -------------------------------------------------------------- lifecycle
    def start(self) -> None:
        """Load models in the background and become ready."""
        self._submit(self._load)

    def _load(self) -> None:
        self._set_state(SessionState.LOADING, "Loading speech model...")
        try:
            device = self._stt.load()
        except Exception as exc:  # any load failure must be shown, not crash the worker
            logger.exception("Speech model failed to load")
            self._emit(ErrorRaised(f"Speech model failed to load: {exc}"))
            return
        logger.info("Speech model ready on %s", device)
        try:
            self._tutor.check()
        except Exception as exc:  # a failed check only warns; turns report errors again
            logger.warning("Tutor model check failed: %s", exc)
            self._emit(ErrorRaised(str(exc)))
        if not self._tts.available:
            self._emit(ErrorRaised("Voice output unavailable: replies are text-only."))
        self._set_state(SessionState.IDLE, f"Ready: hold {self._ptt_label}")

    def set_input_device(self, index: int | None) -> None:
        """Choose the microphone used by the next recording."""
        self._device_index = index

    def on_level(self, value: float) -> None:
        """Forward a microphone level reading to the UI."""
        self._emit(LevelChanged(value))

    def shutdown(self) -> None:
        """Stop background work; abandon any recording in progress."""
        if self.state is SessionState.RECORDING:
            try:
                with self._recorder_lock:
                    self._recorder.stop()
            except Exception:  # shutting down: nothing useful to do with the error
                logger.exception("Recorder failed to stop during shutdown")
        self._runner.close()

    # ------------------------------------------------------------------- turn
    def on_ptt_press(self) -> None:
        """Start recording; ignored unless the session is idle."""
        if not self._transition(SessionState.IDLE, SessionState.RECORDING, "Listening..."):
            return
        try:
            with self._recorder_lock:
                self._recorder.start(self._device_index)
        except Exception as exc:  # device errors vary by driver
            logger.exception("Could not start recording")
            self._emit(ErrorRaised(f"Could not start recording: {exc}"))
            self._set_state(SessionState.IDLE, "Ready")

    def on_ptt_release(self) -> None:
        """Stop recording and process the turn; ignored unless recording."""
        with self._lock:
            if self._state is not SessionState.RECORDING:
                return
            self._state = SessionState.TRANSCRIBING
        self._emit(StateChanged(SessionState.TRANSCRIBING, "Transcribing..."))
        self._submit(self._process_turn)

    def _process_turn(self) -> None:
        try:
            with self._recorder_lock:
                clip = self._recorder.stop()
        except Exception as exc:  # device errors vary by driver
            logger.exception("Could not stop recording")
            self._fail(f"Recording failed: {exc}")
            return
        audio = prepare_for_stt(clip)
        if audio is None:
            self._set_state(SessionState.IDLE, "Too short or too quiet, try again")
            return
        try:
            transcript = self._stt.transcribe(audio)
        except Exception as exc:  # Whisper/CUDA raise assorted runtime errors
            logger.exception("Transcription failed")
            self._fail(f"Transcription failed: {exc}")
            return
        raw = transcript.text  # S4: never rewritten past this point
        if not raw.strip():
            self._set_state(SessionState.IDLE, "Didn't catch that, try again")
            return
        self._emit(UserSaid(raw))
        self._set_state(SessionState.THINKING, "Thinking...")
        try:
            reply = self._tutor.reply(self._history.messages(), raw)
        except LlmUnavailable as exc:
            logger.warning("Tutor model unavailable: %s", exc)
            self._fail(str(exc))
            return
        except AdapterError as exc:
            logger.exception("Tutor model failed")
            self._fail(f"Tutor model failed: {exc}")
            return
        corrections = filter_corrections(raw, reply.corrections)
        live, _ = pick_live(corrections)
        self._turns.append(
            Turn(len(self._turns) + 1, raw, reply.reply, corrections, live)
        )
        self._history.add_exchange(raw, reply.reply)
        self._emit(TutorSaid(reply.reply, live))
        self._speak(self._compose_speech(reply.reply, live))
        self._set_state(SessionState.IDLE, "Ready")

    @staticmethod
    def _compose_speech(reply: str, live: Correction | None) -> str:
        return f"{spoken_line(live)} {reply}" if live is not None else reply

    def _speak(self, text: str) -> None:
        if not self._tts.available:
            return
        self._set_state(SessionState.SPEAKING, "Speaking...")
        try:
            self._tts.speak(text)
        except TtsError as exc:
            logger.warning("Speech synthesis failed, continuing text-only: %s", exc)
        except Exception as exc:  # audio stacks raise assorted errors; keep the text
            logger.exception("Unexpected speech synthesis error")
            self._emit(ErrorRaised(f"Voice output failed: {exc}"))

    # ----------------------------------------------------------------- report
    def end_session(self) -> None:
        """Build the end-of-session report; ignored unless the session is idle."""
        if self._transition(SessionState.IDLE, SessionState.REPORTING, "Writing feedback..."):
            self._submit(self._build_report)

    def _build_report(self) -> None:
        turns = tuple(self._turns)
        majors, minors = self._collect_errors(turns)
        feedback = None
        feedback_error = None
        if turns:
            try:
                feedback = self._tutor.feedback(turns)
            except Exception as exc:  # the recorded errors are still worth reporting
                logger.warning("Feedback generation failed: %s", exc)
                feedback_error = str(exc)
        report = SessionReport(len(turns), majors, minors, feedback, feedback_error)
        self._emit(ReportReady(report))
        if feedback is not None and feedback.summary:
            self._speak(feedback.summary)
        self._turns.clear()
        self._history.clear()
        self._set_state(SessionState.IDLE, "Ready")

    @staticmethod
    def _collect_errors(
        turns: tuple[Turn, ...],
    ) -> tuple[tuple[Correction, ...], tuple[Correction, ...]]:
        every = [c for turn in turns for c in turn.corrections]
        majors = dedupe(c for c in every if c.severity is Severity.MAJOR)
        minors = dedupe(c for c in every if c.severity is Severity.MINOR)
        return majors, minors
