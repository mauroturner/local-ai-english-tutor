"""Builds the end-of-session report from the recorded turns."""

from __future__ import annotations

import logging

from ..domain.corrections import dedupe
from ..domain.models import Correction, SessionReport, Severity, Turn
from ..ports import TutorModel

logger = logging.getLogger(__name__)


def collect_errors(
    turns: tuple[Turn, ...],
) -> tuple[tuple[Correction, ...], tuple[Correction, ...]]:
    """Return the unique major and minor corrections of ``turns``."""
    every = [c for turn in turns for c in turn.corrections]
    majors = dedupe(c for c in every if c.severity is Severity.MAJOR)
    minors = dedupe(c for c in every if c.severity is Severity.MINOR)
    return majors, minors


def make_report(tutor: TutorModel, turns: tuple[Turn, ...]) -> SessionReport:
    """Collect the errors and ask the tutor for feedback (failures are kept as text)."""
    majors, minors = collect_errors(turns)
    feedback = None
    feedback_error = None
    if turns:
        try:
            feedback = tutor.feedback(turns)
        except Exception as exc:  # the recorded errors are still worth reporting
            logger.warning("Feedback generation failed: %s", exc)
            feedback_error = str(exc)
    return SessionReport(len(turns), majors, minors, feedback, feedback_error)
