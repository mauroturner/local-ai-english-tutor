"""Who the learner is: the name and pronouns the tutor uses (pure)."""

from __future__ import annotations

import re
from dataclasses import dataclass

PRONOUNS: dict[str, str] = {"he": "he/him", "she": "she/her", "they": "they/them"}
"""Stored value -> how the pronouns are written in the prompts."""

LEVELS = ("A2", "B1", "B2", "C1")
DEFAULT_LEVEL = "B1"

LEVEL_RULES: dict[str, str] = {
    "A2": "Use only very common words and short sentences (under 10 words). Stay on familiar "
    "topics. Report at most ONE error per message: the most important one.",
    "B1": "Use everyday vocabulary and sentences of up to about 15 words. Report at most TWO "
    "errors per message.",
    "B2": "Use natural vocabulary, including common phrasal verbs and idioms, and normal "
    "sentences. Report up to THREE errors per message.",
    "C1": "Use rich, precise vocabulary, idioms and varied sentences. Also report subtle "
    "errors of word choice, collocation and register.",
}
"""Level -> how the tutor should talk and how many corrections to give (CEFR)."""

SLOW_SPEECH = {"A2": 1.15}
"""Level -> Piper ``length_scale`` (above 1 is slower); other levels use 1.0."""

MAX_NAME_CHARS = 40
_FORBIDDEN_NAME_CHARS = frozenset('"\\{}<>`')
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class LearnerProfile:
    """The learner's name (may be empty) and pronoun key (see ``PRONOUNS``)."""

    name: str = "Mauro"
    pronouns: str = "he"
    level: str = DEFAULT_LEVEL
    explain_in: str = "en"  # language of the explanation of each correction ("en" or "es")


def name_error(text: str) -> str | None:
    """Why ``text`` cannot be used as the learner's name, or None when it can.

    An empty name is allowed: the tutor then simply does not use a name.
    """
    name = text.strip()
    if len(name) > MAX_NAME_CHARS:
        return f"Use at most {MAX_NAME_CHARS} characters."
    if any(ch in _FORBIDDEN_NAME_CHARS or not ch.isprintable() for ch in name):
        return "Use letters, spaces and simple punctuation only."
    return None


def clean_name(text: str) -> str:
    """The name as stored: surrounding spaces removed, inner spaces collapsed."""
    return _SPACE_RE.sub(" ", text).strip()


def profile_block(profile: LearnerProfile) -> str:
    """The LEARNER section appended to every system prompt."""
    pronouns = PRONOUNS.get(profile.pronouns, PRONOUNS["they"])
    lines = ["LEARNER:"]
    name = clean_name(profile.name)
    if name:
        lines.append(f'- Name: "{name}". Use it now and then, not in every message.')
    else:
        lines.append("- The learner has not given a name: do not use or invent one.")
    lines.append(
        f"- Pronouns: {pronouns}. Use them whenever you refer to the learner "
        "in the third person."
    )
    level = profile.level if profile.level in LEVEL_RULES else DEFAULT_LEVEL
    lines.append(f"- English level (CEFR): {level}. {LEVEL_RULES[level]}")
    return "\n".join(lines)


def explanation_rule(profile: LearnerProfile) -> str:
    """The turn-prompt line asking for Spanish explanations; empty for English."""
    if profile.explain_in != "es":
        return ""
    return (
        'EXPLANATION LANGUAGE: write the "explanation" of every error in simple Spanish. '
        'Keep "original", "corrected" and "reply" in English.'
    )


def speech_scale(level: str) -> float:
    """Piper ``length_scale`` for the learner's level: slower for beginners."""
    return SLOW_SPEECH.get(level, 1.0)


def with_profile(prompt: str, profile: LearnerProfile) -> str:
    """``prompt`` followed by the LEARNER section (concatenated, never ``str.format``)."""
    return prompt.rstrip("\n") + "\n\n" + profile_block(profile)
