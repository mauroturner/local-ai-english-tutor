"""Who the learner is: the name and pronouns the tutor uses (pure)."""

from __future__ import annotations

import re
from dataclasses import dataclass

PRONOUNS: dict[str, str] = {"he": "he/him", "she": "she/her", "they": "they/them"}
"""Stored value -> how the pronouns are written in the prompts."""

MAX_NAME_CHARS = 40
_FORBIDDEN_NAME_CHARS = frozenset('"\\{}<>`')
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class LearnerProfile:
    """The learner's name (may be empty) and pronoun key (see ``PRONOUNS``)."""

    name: str = "Mauro"
    pronouns: str = "he"


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
    return "\n".join(lines)


def with_profile(prompt: str, profile: LearnerProfile) -> str:
    """``prompt`` followed by the LEARNER section (concatenated, never ``str.format``)."""
    return prompt.rstrip("\n") + "\n\n" + profile_block(profile)
