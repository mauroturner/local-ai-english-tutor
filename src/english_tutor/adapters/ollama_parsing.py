"""Tolerant parsing of the tutor model's JSON answers."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..domain.categories import parse_category
from ..domain.vocabulary import PhraseSuggestion, clean_suggestion
from ..domain.models import (
    Correction,
    PracticeOutcome,
    PracticeReply,
    SessionFeedback,
    Severity,
    TutorReply,
)

logger = logging.getLogger(__name__)

FALLBACK_REPLY = "Sorry, I lost my train of thought. Could you say that again?"
FALLBACK_SUMMARY = "I could not write the feedback this time."
FALLBACK_PROMPT = "Let's keep going. Tell me about your day."


def _first_json_object(raw: str) -> dict[str, Any] | None:
    """Return the first balanced ``{...}`` object found in ``raw``, if it parses."""
    start = raw.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for pos in range(start, len(raw)):
            ch = raw[pos]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(raw[start : pos + 1])
                    except json.JSONDecodeError:
                        break
                    return data if isinstance(data, dict) else None
        start = raw.find("{", start + 1)
    return None


def _load_object(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _first_json_object(raw) if isinstance(raw, str) else None
    return data if isinstance(data, dict) else _first_json_object(raw)


_MODEL_SEVERITIES = (Severity.MAJOR, Severity.MINOR)
"""What the model may report; long pauses are measured by the app, never reported."""


def _parse_correction(item: Any) -> Correction | None:
    if not isinstance(item, dict):
        return None
    try:
        severity = Severity(str(item["severity"]).strip().lower())
        original = str(item["original"]).strip()
        corrected = str(item["corrected"]).strip()
        explanation = str(item["explanation"]).strip()
    except (KeyError, ValueError):
        return None
    if severity not in _MODEL_SEVERITIES or not original or not corrected:
        return None
    return Correction(original, corrected, explanation, severity, parse_category(item.get("category")))


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(v).strip() for v in value if str(v).strip())


def parse_tutor_reply(raw: str) -> TutorReply:
    """Parse a turn answer; never raises. Unparseable text becomes the reply."""
    data = _load_object(raw)
    if data is None or not isinstance(data.get("reply"), str):
        logger.warning("Tutor answer was not valid JSON; using raw text")
        return TutorReply(reply=raw.strip() or FALLBACK_REPLY, corrections=(), parsed_ok=False)
    errors = data.get("errors")
    parsed = [_parse_correction(e) for e in errors] if isinstance(errors, list) else []
    corrections = tuple(c for c in parsed if c is not None)
    natural = data.get("natural")
    return TutorReply(
        reply=data["reply"].strip() or FALLBACK_REPLY,
        corrections=corrections,
        parsed_ok=True,
        natural=(natural.strip() or None) if isinstance(natural, str) else None,
    )


def parse_feedback(raw: str) -> SessionFeedback:
    """Parse the session feedback; never raises."""
    data = _load_object(raw)
    if data is None or not isinstance(data.get("summary"), str):
        logger.warning("Feedback was not valid JSON; using raw text")
        return SessionFeedback(summary=raw.strip() or FALLBACK_SUMMARY)
    return SessionFeedback(
        summary=data["summary"].strip() or FALLBACK_SUMMARY,
        strengths=_string_list(data.get("strengths")),
        focus_areas=_string_list(data.get("focus_areas")),
        memory=memory if isinstance(memory := data.get("memory"), str) else "",
    )


def _outcome(value: Any) -> PracticeOutcome:
    try:
        return PracticeOutcome(str(value).strip().lower())
    except ValueError:
        return PracticeOutcome.NOT_USED


def parse_practice_reply(raw: str) -> PracticeReply:
    """Parse a practice answer; never raises. Unparseable text becomes the next question."""
    data = _load_object(raw)
    if data is None or not {"target_used", "feedback", "next_prompt"} & data.keys():
        logger.warning("Practice answer was not valid JSON; using raw text")
        return PracticeReply(
            PracticeOutcome.NOT_USED, "", raw.strip() or FALLBACK_PROMPT, parsed_ok=False
        )
    feedback, prompt = data.get("feedback"), data.get("next_prompt")
    return PracticeReply(
        outcome=_outcome(data.get("target_used")),
        feedback=feedback.strip() if isinstance(feedback, str) else "",
        next_prompt=(prompt.strip() if isinstance(prompt, str) else "") or FALLBACK_PROMPT,
    )


def parse_phrase(raw: str) -> PhraseSuggestion | None:
    """Parse a phrase suggestion; None when there is no usable phrase. Never raises."""
    data = _load_object(raw)
    if data is None or not isinstance(data.get("phrase"), str):
        return None
    meaning, example = data.get("meaning"), data.get("example")
    return clean_suggestion(
        PhraseSuggestion(
            data["phrase"],
            meaning if isinstance(meaning, str) else "",
            example if isinstance(example, str) else "",
        )
    )
