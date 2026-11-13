"""Prompt, schema and builder for the targeted practice drill."""

from __future__ import annotations

import re

from .learner import LearnerProfile, with_profile
from .models import MistakeRecord, Severity

PRACTICE_START = "START"
_MAX_FIELD_CHARS = 200
_SPACE_RE = re.compile(r"\s+")

PRACTICE_SCHEMA = {
    "type": "object",
    "properties": {
        "target_used": {"type": "string", "enum": ["correct", "incorrect", "not_used"]},
        "feedback": {"type": "string"},
        "next_prompt": {"type": "string"},
    },
    "required": ["target_used", "feedback", "next_prompt"],
}

PRACTICE_SYSTEM_PROMPT = """\
You are Alex, a friendly English tutor running a short SPEAKING drill. The learner's messages are
automatic speech-to-text transcripts. The drill practices ONE structure, described in TARGET below.

Every answer is JSON with three fields, in this order:
1. "target_used": judge ONLY the target structure in the learner's last message.
   - "correct": they used the correct form, or the same rule correctly with other words.
   - "incorrect": they used the structure but made the same kind of mistake again.
   - "not_used": they did not use the structure, or the message is START.
   If you are not sure it is wrong, it is "correct". Ignore every other mistake.
   Never judge punctuation, capitalization or spelling (the text comes from speech recognition).
2. "feedback": ONE short sentence.
   - "correct": praise briefly and say what was right.
   - "incorrect": give the corrected version of their sentence.
   - "not_used": kindly remind them to use the structure.
   - START: say in one sentence what you will practice together.
3. "next_prompt": ONE short, simple question about the learner's life (yesterday, plans, habits,
   likes) that makes them naturally use the correct form in their answer.
   Never include the answer. Never repeat a question you already asked.
Spoken English only: no lists, no emojis, no markdown.
Answer ONLY with JSON: {"target_used": "...", "feedback": "...", "next_prompt": "..."}

Example (said "I go", correct form "I went", rule: use the past tense for finished actions):
Learner: START
{"target_used": "not_used", "feedback": "Let's practice talking about the past.", "next_prompt": "Where did you go last weekend?"}
Learner: last weekend I go to the beach
{"target_used": "incorrect", "feedback": "Almost! Say: last weekend I went to the beach.", "next_prompt": "What did you eat for dinner yesterday?"}
Learner: I ate pizza with my friends
{"target_used": "correct", "feedback": "Perfect, 'I ate' is the right past form!", "next_prompt": "Who did you talk to this morning?"}
"""


def _clean(text: str) -> str:
    """Make stored text safe to embed in the prompt: one line, no double quotes, bounded."""
    collapsed = _SPACE_RE.sub(" ", text).strip().replace('"', "'")
    return collapsed[:_MAX_FIELD_CHARS]


def target_block(target: MistakeRecord) -> str:
    """The TARGET section describing the mistake (or the long pause) being practised."""
    if target.severity is Severity.HESITATION:
        return (
            "TARGET (fluency, not a grammar mistake):\n"
            f'- The learner paused for a long time while saying: "{_clean(target.original)}"\n'
            f'- Goal: say "{_clean(target.corrected)}" smoothly, in one go.\n'
            '- "target_used": "correct" when they said this phrase (or nearly the same words), '
            'otherwise "not_used". Never "incorrect": the app measures the pauses itself.\n'
            "- Ask questions whose natural answer contains this phrase."
        )
    if target.severity is Severity.VOCABULARY:
        return (
            "TARGET (vocabulary, not a mistake):\n"
            f'- The learner is learning this English phrase: "{_clean(target.corrected)}"'
            f' (meaning: "{_clean(target.original)}").\n'
            f'- Example: "{_clean(target.explanation)}"\n'
            '- "target_used": "correct" when they used the phrase naturally (small changes of '
            'tense or person are fine), "incorrect" when they used it wrongly, "not_used" '
            "otherwise.\n"
            "- Ask questions whose natural answer contains this phrase."
        )
    return (
        "TARGET:\n"
        f'- The learner said: "{_clean(target.original)}"\n'
        f'- Correct form: "{_clean(target.corrected)}"\n'
        f"- Rule: {_clean(target.explanation)}"
    )


def build_practice_system_prompt(
    target: MistakeRecord, profile: LearnerProfile | None = None
) -> str:
    """System prompt for a drill on ``target`` (concatenated, never ``str.format``)."""
    prompt = PRACTICE_SYSTEM_PROMPT + "\n" + target_block(target)
    return with_profile(prompt, profile or LearnerProfile())
