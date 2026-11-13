"""Targeted practice: the drill state and the two session steps built on it."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from ..domain.formatting import practice_speech
from ..domain.hesitation import pause_inside, retry_feedback
from ..domain.models import Hesitation, MistakeRecord, PracticeOutcome, PracticeReply, Severity
from ..domain.practice_prompts import PRACTICE_START
from ..ports import LogSpeaker, PracticeCoach
from .events import EventSink, MistakesChanged, PracticeChanged, PracticeFeedback, TutorSaid
from .history import ChatHistory
from .mistake_book import MistakeBook


class PracticeDrill:
    """One practice conversation about a single mistake.

    It keeps its own bounded history, separate from the normal conversation.
    A failed coach call leaves the history unchanged.
    """

    def __init__(self, target: MistakeRecord, history_exchanges: int = 4) -> None:
        self._target = target
        self._history = ChatHistory(history_exchanges)

    @property
    def target(self) -> MistakeRecord:
        """The mistake being practised."""
        return self._target

    def open(self, coach: PracticeCoach) -> PracticeReply:
        """Ask the coach to introduce the drill."""
        return self._ask(coach, PRACTICE_START)

    def answer(self, coach: PracticeCoach, text: str) -> PracticeReply:
        """Send the learner's raw transcript and return the coach's judgement."""
        return self._ask(coach, text)

    def _ask(self, coach: PracticeCoach, text: str) -> PracticeReply:
        reply = coach.practice(self._target, self._history.messages(), text)
        self._history.add_exchange(text, practice_speech(reply))
        return reply


@dataclass(frozen=True)
class PracticeServices:
    """The session capabilities the practice steps need."""

    ask: Callable[[Callable[[], PracticeReply]], PracticeReply | None]
    emit: EventSink
    journal: Callable[[LogSpeaker, str], None]
    speak: Callable[[str], None]


def open_practice(drill: PracticeDrill, coach: PracticeCoach, svc: PracticeServices) -> bool:
    """Introduce ``drill``; False when the coach failed (the caller stays in conversation)."""
    reply = svc.ask(lambda: drill.open(coach))
    if reply is None:
        return False
    speech = practice_speech(reply)
    target = drill.target
    svc.emit(PracticeChanged(target))
    svc.emit(TutorSaid(speech))
    svc.journal("practice", f"Started: '{target.original}' -> '{target.corrected}'")
    svc.journal("tutor", speech)
    svc.speak(speech)
    return True


def judge_fluency(
    target: MistakeRecord, reply: PracticeReply, pauses: Sequence[Hesitation]
) -> PracticeReply:
    """For a pause item, a phrase used with a long pause inside it is not yet correct.

    The coach only sees text, so it cannot hear pauses; the measured timings decide.
    """
    if target.severity is not Severity.HESITATION or reply.outcome is not PracticeOutcome.CORRECT:
        return reply
    pause = pause_inside(target.corrected, pauses)
    if pause is None:
        return reply
    return replace(reply, outcome=PracticeOutcome.INCORRECT, feedback=retry_feedback(pause))


def run_practice_turn(
    drill: PracticeDrill,
    coach: PracticeCoach,
    raw: str,
    book: MistakeBook,
    svc: PracticeServices,
    pauses: Sequence[Hesitation] = (),
) -> bool:
    """Judge one answer; False when the coach failed (the drill stays active)."""
    reply = svc.ask(lambda: drill.answer(coach, raw))
    if reply is None:
        return False
    reply = judge_fluency(drill.target, reply, pauses)
    if reply.parsed_ok and reply.outcome is not PracticeOutcome.NOT_USED:
        book.add_practice(drill.target.key, reply.outcome)
        svc.emit(MistakesChanged(book.snapshot()))
    svc.emit(PracticeFeedback(reply.outcome, reply.feedback, reply.next_prompt))
    svc.journal("practice", f"[{reply.outcome.value}] {reply.feedback}")
    svc.journal("tutor", reply.next_prompt)
    svc.speak(practice_speech(reply))
    return True
