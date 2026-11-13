"""What the learner can ask for while the session is idle: scenarios, replay and drills.

These methods are the public actions of ``ConversationSession`` that are not the turn
pipeline itself. They live here only to keep the session file small; they use the
state of the session (its lock, state, drills, tutor and voice), so the class is a
mixin that is not meant to be used on its own.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..domain.drills import DrillKind
from ..domain.models import Hesitation, SessionState
from ..domain.scenarios import get_scenario
from ..domain.models import PracticeOutcome
from .events import (
    ErrorRaised,
    PhraseSaved,
    PracticeChanged,
    ScenarioChanged,
    StateChanged,
    TutorSaid,
    VocabularyChanged,
)
from .practice import PracticeDrill, open_practice, run_practice_turn

SLOWER_SPEECH = 1.35
"""How much "repeat slower" stretches the speech, on top of the level's own pace."""

Pauses = tuple[Hesitation, ...]


class SessionActions:
    """Scenario choice, replay, listening drills and practice drills of the session."""

    # Provided by ConversationSession (declared for readers; see its __init__).
    _lock: Any
    _state: SessionState
    _drill: PracticeDrill | None
    _listen: Any
    _turns: list[Any]
    _tts: Any
    _coach: Any
    _book: Any
    _practice: Any
    _scenario: Any
    _last_spoken: str
    _vocab: Any
    _phrases: Any
    _emit: Callable[[Any], None]
    _journal: Any

    def set_scenario(self, key: str) -> None:
        """Pick a role-play scenario; ignored unless idle, not practicing and before any answer.

        The tutor opens the scenario with its first line (shown, logged and spoken).
        """
        with self._lock:
            if self._state is not SessionState.IDLE or self._practicing() or self._turns:
                return
            self._state = SessionState.THINKING
        self._emit(StateChanged(SessionState.THINKING, "Setting the scene..."))
        self._submit(lambda: self._start_scenario(key))

    def _start_scenario(self, key: str) -> None:
        chosen = self._scenario.set(key)
        self._emit(ScenarioChanged(chosen))
        scenario = get_scenario(chosen)
        if scenario is not None:
            self._emit(TutorSaid(scenario.opening))
            self._journal.record("tutor", scenario.opening)
            self._speak(scenario.opening)
        self._set_state(SessionState.IDLE, self._ready_message())

    def repeat_last(self, slower: bool = False) -> None:
        """Say the tutor's last words again (``slower`` stretches them); ignored unless idle."""
        with self._lock:
            if self._state is not SessionState.IDLE or not self._last_spoken:
                return
            if not self._tts.available:
                return
            self._state = SessionState.SPEAKING
        self._submit(lambda: self._replay(slower))

    def _replay(self, slower: bool) -> None:
        self._speak(self._last_spoken, SLOWER_SPEECH if slower else 1.0)
        self._set_state(SessionState.IDLE, self._ready_message())

    # ------------------------------------------------------------------ word list
    def save_phrase(self) -> None:
        """Add a phrase from the tutor's last words to the word list; ignored unless idle."""
        with self._lock:
            ready = (
                self._state is SessionState.IDLE
                and not self._practicing()
                and self._phrases is not None
                and bool(self._last_reply())
            )
            if ready:
                self._state = SessionState.THINKING
        if not ready:
            return
        self._emit(StateChanged(SessionState.THINKING, "Choosing a phrase..."))
        self._submit(lambda: self._save_phrase_job(self._last_reply(), False))

    def _last_reply(self) -> str:
        return self._turns[-1].tutor_reply if self._turns else self._last_spoken

    def _save_phrase_job(self, text: str, spanish: bool) -> None:
        suggestion = self._ask(lambda: self._phrases.suggest_phrase(text, spanish))
        entry = self._vocab.add(suggestion) if suggestion is not None else None
        if entry is not None:
            self._emit(VocabularyChanged(self._vocab.snapshot()))
            self._emit(PhraseSaved(entry))
            self._journal.record("tutor", f"Saved phrase: {entry.phrase} ({entry.meaning})")
            if spanish:
                said = f"You can say: {entry.phrase}."
                if entry.example:
                    said += f" For example: {entry.example}"
                self._emit(TutorSaid(said))
                self._speak(said)
        self._set_state(SessionState.IDLE, self._ready_message())

    def _phrase_request(self, spanish_text: str) -> None:
        """Answer "how do I say ..." (already transcribed in Spanish) with a saved phrase."""
        self._set_state(SessionState.THINKING, "Looking for the English phrase...")
        self._save_phrase_job(spanish_text, True)

    def remove_phrase(self, key: str) -> None:
        """Delete a phrase from the word list; ignored unless idle."""
        with self._lock:
            if self._state is not SessionState.IDLE:
                return
        self._submit(lambda: self._forget_phrase(key))

    def _forget_phrase(self, key: str) -> None:
        self._vocab.remove(key)
        self._emit(VocabularyChanged(self._vocab.snapshot()))

    def _vocabulary_result(self, key: str, outcome: PracticeOutcome) -> None:
        """A drill on a saved phrase ended with ``outcome``: move its review date."""
        self._vocab.practice(key, outcome)
        self._emit(VocabularyChanged(self._vocab.snapshot()))

    def _practicing(self) -> bool:
        """Whether a practice or listening drill is running (the lock is held by callers)."""
        return self._drill is not None or self._listen.active

    # ------------------------------------------------- listening and speaking drills
    def start_listening(self, kind: DrillKind) -> None:
        """Start a shadowing, minimal-pair or dictation drill; ignored unless idle and free.

        Shadowing and dictation need the voice; pairs are read from the screen.
        """
        with self._lock:
            if self._state is not SessionState.IDLE or self._practicing():
                return
            if kind is not DrillKind.PAIRS and not self._tts.available:
                return
            self._state = SessionState.THINKING
        self._emit(StateChanged(SessionState.THINKING, "Preparing the drill..."))
        self._submit(lambda: self._listening_job(lambda: self._listen.open(kind)))

    def next_listening(self) -> None:
        """Move to another sentence of the running drill; ignored unless idle."""
        self._listening_step(self._listen.next)

    def stop_listening(self) -> None:
        """Leave the running drill; ignored unless idle."""
        self._listening_step(self._listen.close)

    def submit_dictation(self, text: str) -> None:
        """Check the text the learner typed; ignored unless a dictation is waiting for it."""
        if text.strip() and self._listen.kind is DrillKind.DICTATION:
            self._listening_step(lambda: self._listen.answer(text))

    def _listening_step(self, action: Callable[[], object]) -> None:
        with self._lock:
            if self._state is not SessionState.IDLE or not self._listen.active:
                return
            self._state = SessionState.THINKING
        self._emit(StateChanged(SessionState.THINKING, "Checking..."))
        self._submit(lambda: self._listening_job(action))

    def _listening_job(self, action: Callable[[], object]) -> None:
        action()
        self._set_state(SessionState.IDLE, self._ready_message())

    def _listening_turn(self, raw: str) -> None:
        """A spoken answer during a drill (typing is how dictation is answered)."""
        if self._listen.kind is DrillKind.DICTATION:
            self._emit(ErrorRaised("Type what you heard in the box and press Check."))
            self._set_state(SessionState.IDLE, self._ready_message())
            return
        self._set_state(SessionState.THINKING, "Checking your answer...")
        self._listening_job(lambda: self._listen.answer(raw))

    # --------------------------------------------------------------- practice
    def start_practice(self, key: str) -> None:
        """Start a drill on the mistake ``key``; ignored unless idle and not practicing."""
        with self._lock:
            if self._state is not SessionState.IDLE or self._practicing():
                return
            self._state = SessionState.THINKING
        self._emit(StateChanged(SessionState.THINKING, "Preparing practice..."))
        self._submit(lambda: self._open_practice(key))

    def _open_practice(self, key: str) -> None:
        record = self._book.get(key) or self._vocab.target(key)
        if self._coach is None or record is None:
            self._fail("Practice is not available for that mistake.")
            return
        drill = PracticeDrill(record)
        if open_practice(drill, self._coach, self._practice):
            with self._lock:
                self._drill = drill
            self._set_state(SessionState.IDLE, self._ready_message())

    def _practice_turn(self, drill: PracticeDrill, raw: str, pauses: Pauses) -> None:
        if self._coach is None:
            self._fail("Practice is not available.")
            return
        self._set_state(SessionState.THINKING, "Checking your answer...")
        if run_practice_turn(drill, self._coach, raw, self._book, self._practice, pauses):
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
