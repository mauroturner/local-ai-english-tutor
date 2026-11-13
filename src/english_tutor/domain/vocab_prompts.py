"""Prompts and schema that ask the model for a phrase to learn (pure)."""

from __future__ import annotations

MAX_INPUT_CHARS = 400

PHRASE_SCHEMA = {
    "type": "object",
    "properties": {
        "phrase": {"type": "string"},
        "meaning": {"type": "string"},
        "example": {"type": "string"},
    },
    "required": ["phrase", "meaning", "example"],
}

_FROM_REPLY = """\
You help a Spanish-speaking learner build a personal word list. You receive something the tutor
just said in English. Pick ONE word or phrase from it that an intermediate learner would like to
learn (not a very basic word).
- "phrase": the exact English words, 1 to 5 words.
- "meaning": a short translation or explanation in Spanish.
- "example": one short, simple English sentence that uses the phrase.
Plain text only. Answer ONLY with JSON: {"phrase": "...", "meaning": "...", "example": "..."}
Example:
Tutor said: That sounds like a lot of fun! Do you often go hiking?
{"phrase": "a lot of fun", "meaning": "muy divertido", "example": "The party was a lot of fun."}
"""

_FROM_SPANISH = """\
A Spanish-speaking learner of English asked, in Spanish, how to say something in English. Give the
natural English way to say it.
- "phrase": the English words, as short and natural as possible (1 to 8 words).
- "meaning": what the learner asked, in Spanish, shortened.
- "example": one short, simple English sentence that uses the phrase.
Plain text only. Never answer in Spanish except in "meaning". Answer ONLY with JSON:
{"phrase": "...", "meaning": "...", "example": "..."}
Example:
Learner asked: como se dice tengo ganas de salir
{"phrase": "I feel like going out", "meaning": "tengo ganas de salir", "example": "I feel like going out tonight."}
"""


def phrase_system_prompt(spanish: bool) -> str:
    """The system prompt for a phrase suggestion (``spanish``: the learner asked in Spanish).

    It has no LEARNER section on purpose: with the learner's name in the prompt the
    model puts it in the example sentences.
    """
    return _FROM_SPANISH if spanish else _FROM_REPLY


def phrase_user_message(text: str, spanish: bool) -> str:
    """The user message: the tutor's reply or the learner's Spanish request, bounded."""
    clean = " ".join(text.split())[:MAX_INPUT_CHARS]
    return f"Learner asked: {clean}" if spanish else f"Tutor said: {clean}"
