"""Conversation session: the state machine behind every learner turn."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Literal, TypeVar

from ..audio.processing import prepare_for_stt
from ..domain.corrections import filter_corrections, pick_live, spoken_line
from ..domain.formatting import correction_text, format_report
from ..domain.models import Correction, SessionState, Turn
from ..ports import (
    AdapterError,
    AudioRecorder,
    ConversationLog,
    LlmUnavailable,
    MistakeStore,
    PracticeCoach,
    SpeechSynthesizer,
    SpeechToText,
    TtsError,
    TutorModel,
)
from .events import (
    ErrorRaised,
    EventSink,
    LevelChanged,
    MistakesChanged,
    PracticeChanged,
    ReportReady,
    StateChanged,
    TutorSaid,
    UserSaid,
)
from .history import ChatHistory
from .journal import NullConversationLog, NullMistakeStore, SafeJournal
from .mistake_book import MistakeBook
from .practice import PracticeDrill, PracticeServices, open_practice, run_practice_turn
from .report import make_report
from .worker import Runner, SerialWorker

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class ConversationSession:
    """Coordinates recording, transcription, the tutor model and speech.

    Threading model: ``on_ptt_press`` / ``on_ptt_release`` / ``end_session`` may
    be called from any thread and never block on slow work. All slow work and
    all mutation of ``turns`` and history happen on the runner (one job at a
    time). The state is guarded by a lock. The microphone is opened and closed
    on the runner too. Lock order: ``_recorder_lock`` first, then ``_lock``;
    never take ``_recorder_lock`` while holding ``_lock``.
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
        ptt_label: str = "V",
        conversation_log: ConversationLog | None = None,
        mistakes: MistakeStore | None = None,
        coach: PracticeCoach | None = None,
    ) -> None:
        self._stt = stt
        self._tutor = tutor
        self._tts = tts
        self._recorder = recorder
        self._emit = emit
        self._runner: Runner = runner if runner is not None else SerialWorker()
        self._ptt_label = ptt_label
        self._warned: set[str] = set()
        self._journal = SafeJournal(
            conversation_log or NullConversationLog(),
            lambda message: self._warn_once("log", message),
        )
        self._coach = coach
        self._drill: PracticeDrill | None = None
        self._practice = PracticeServices(
            self._ask, self._emit, self._journal.record, self._speak
        )
        self._book = MistakeBook(
            mistakes or NullMistakeStore(),
            lambda message: self._warn_once("mistakes", message),
        )
        self._history = ChatHistory(history_exchanges)
        self._turns: list[Turn] = []
        self._state = SessionState.LOADING
        self._lock = threading.Lock()
        self._recorder_lock = threading.Lock()
        self._mic: Literal["closed", "open", "failed"] = "closed"
        self._closing = False
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

    def _warn_once(self, source: str, message: str) -> None:
        """Show ``message`` to the learner the first time ``source`` fails."""
        if source not in self._warned:
            self._warned.add(source)
            self._emit(ErrorRaised(message))

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
        self._book.load()
        self._emit(MistakesChanged(self._book.snapshot()))
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

    def shutdown(self, timeout_s: float = 2.0) -> None:
        """Stop background work; abandon any recording in progress.

        Runs on the UI thread, so it waits at most ``timeout_s`` for a device
        call in progress on the worker; a hung audio driver must not freeze exit.
        """
        with self._lock:
            self._closing = True
        if self._recorder_lock.acquire(timeout=timeout_s):
            try:
                if self._mic == "open":
                    self._mic = "closed"
                    try:
                        self._recorder.stop()
                    except Exception:  # shutting down: nothing useful to do with the error
                        logger.exception("Recorder failed to stop during shutdown")
            finally:
                self._recorder_lock.release()
        else:
            logger.warning("Audio device busy for %.1fs; closing without stopping it", timeout_s)
        self._runner.close()

    # ------------------------------------------------------------------- turn
    def on_ptt_press(self) -> None:
        """Start recording; ignored unless the session is idle."""
        if not self._transition(SessionState.IDLE, SessionState.RECORDING, "Listening..."):
            return
        self._submit(self._start_recording)

    def _start_recording(self) -> None:
        """Open the microphone on the worker (queued before any release job)."""
        with self._recorder_lock:
            with self._lock:
                skip = self._closing or self._state is not SessionState.RECORDING
            if skip:
                return
            try:
                self._recorder.start(self._device_index)
                self._mic = "open"
            except Exception as exc:  # device errors vary by driver
                logger.exception("Could not start recording")
                self._emit(ErrorRaised(f"Could not start recording: {exc}"))
                # If a release already queued the turn, that job returns to IDLE.
                back = self._transition(SessionState.RECORDING, SessionState.IDLE, "Ready")
                self._mic = "closed" if back else "failed"

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
                mic, self._mic = self._mic, "closed"
                clip = self._recorder.stop() if mic == "open" else None
        except Exception as exc:  # device errors vary by driver
            logger.exception("Could not stop recording")
            self._fail(f"Recording failed: {exc}")
            return
        if clip is None:  # the microphone never opened (quick tap or start failure)
            message = "Ready" if mic == "failed" else "Too short or too quiet, try again"
            self._set_state(SessionState.IDLE, message)
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
        self._journal.record("you", raw)
        with self._lock:
            drill = self._drill
        if drill is not None:  # practice answers skip the normal correction pipeline
            self._practice_turn(drill, raw)
            return
        self._set_state(SessionState.THINKING, "Thinking...")
        reply = self._ask(lambda: self._tutor.reply(self._history.messages(), raw))
        if reply is None:
            return
        corrections = filter_corrections(raw, reply.corrections)
        live, _ = pick_live(corrections)
        self._turns.append(
            Turn(len(self._turns) + 1, raw, reply.reply, corrections, live)
        )
        self._history.add_exchange(raw, reply.reply)
        self._emit(TutorSaid(reply.reply, live))
        self._journal.record("tutor", reply.reply)
        if live is not None:
            self._journal.record("tip", correction_text(live))
        self._record_mistakes(corrections, raw)
        self._speak(self._compose_speech(reply.reply, live))
        self._set_state(SessionState.IDLE, "Ready")

    def _ask(self, call: Callable[[], _T]) -> _T | None:
        """Run a model call; on failure show the error, return to IDLE and give None."""
        try:
            return call()
        except LlmUnavailable as exc:
            logger.warning("Tutor model unavailable: %s", exc)
            self._fail(str(exc))
        except AdapterError as exc:
            logger.exception("Tutor model failed")
            self._fail(f"Tutor model failed: {exc}")
        return None

    def _record_mistakes(self, corrections: tuple[Correction, ...], sentence: str) -> None:
        """Add this turn's corrections to the history and tell the UI."""
        if not corrections:
            return
        self._book.add_corrections(corrections, sentence)
        self._emit(MistakesChanged(self._book.snapshot()))

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

    # --------------------------------------------------------------- practice
    def start_practice(self, key: str) -> None:
        """Start a drill on the mistake ``key``; ignored unless idle and not practicing."""
        with self._lock:
            if self._state is not SessionState.IDLE or self._drill is not None:
                return
            self._state = SessionState.THINKING
        self._emit(StateChanged(SessionState.THINKING, "Preparing practice..."))
        self._submit(lambda: self._open_practice(key))

    def _open_practice(self, key: str) -> None:
        record = self._book.get(key)
        if self._coach is None or record is None:
            self._fail("Practice is not available for that mistake.")
            return
        drill = PracticeDrill(record)
        if open_practice(drill, self._coach, self._practice):
            with self._lock:
                self._drill = drill
            self._set_state(SessionState.IDLE, self._ready_message())

    def _practice_turn(self, drill: PracticeDrill, raw: str) -> None:
        if self._coach is None:
            self._fail("Practice is not available.")
            return
        self._set_state(SessionState.THINKING, "Checking your answer...")
        if run_practice_turn(drill, self._coach, raw, self._book, self._practice):
            self._set_state(SessionState.IDLE, self._ready_message())

    def stop_practice(self) -> None:
        """Leave the drill and go back to the conversation; ignored unless idle and practicing."""
        with self._lock:
            if self._state is not SessionState.IDLE or self._drill is None:
                return
            self._drill = None
        self._emit(PracticeChanged(None))
        self._emit(StateChanged(SessionState.IDLE, self._ready_message()))
        self._submit(lambda: self._journal.record("practice", "Stopped practice"))

    def _ready_message(self) -> str:
        with self._lock:
            practicing = self._drill is not None
        if practicing:
            return f"Practice: hold {self._ptt_label} to answer"
        return f"Ready: hold {self._ptt_label}"

    # ----------------------------------------------------------------- report
    def end_session(self) -> None:
        """Build the end-of-session report; ignored unless idle and not practicing."""
        with self._lock:
            if self._state is not SessionState.IDLE or self._drill is not None:
                return
            self._state = SessionState.REPORTING
        self._emit(StateChanged(SessionState.REPORTING, "Writing feedback..."))
        self._submit(self._build_report)

    def _build_report(self) -> None:
        report = make_report(self._tutor, tuple(self._turns))
        self._emit(ReportReady(report))
        self._journal.record("report", format_report(report))
        self._journal.new_session()
        if report.feedback is not None and report.feedback.summary:
            self._speak(report.feedback.summary)
        self._turns.clear()
        self._history.clear()
        self._set_state(SessionState.IDLE, "Ready")
