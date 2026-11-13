"""Listening and speaking drills: choosing targets and judging answers."""

from __future__ import annotations

import random

from english_tutor.domain.drills import (
    FALLBACK_SENTENCES,
    MAX_WORDS,
    MIN_WORDS,
    DrillKind,
    Target,
    _PAIRS,
    judge,
    pick_dictation,
    pick_pair,
    pick_shadow,
    sentences_from,
)


def test_only_sentences_of_a_sensible_length_are_offered():
    reply = "Wow! That sounds like a lovely holiday. What was the best part of the trip for you?"
    assert sentences_from(reply) == [
        "That sounds like a lovely holiday.",
        "What was the best part of the trip for you?",
    ]
    long = " ".join(["word"] * (MAX_WORDS + 1)) + "."
    assert sentences_from(long) == [] and MIN_WORDS == 4


def test_shadowing_uses_the_last_reply_or_a_fixed_sentence():
    rng = random.Random(1)
    assert pick_shadow("Yes! What did you do at the park yesterday?", rng).text == (
        "What did you do at the park yesterday?"
    )
    assert pick_shadow("Hi!", rng).text in FALLBACK_SENTENCES
    assert pick_dictation("", rng).text in FALLBACK_SENTENCES


def test_every_fixed_sentence_has_a_usable_length():
    assert all(MIN_WORDS <= len(s.split()) <= MAX_WORDS for s in FALLBACK_SENTENCES)


def test_a_pair_sentence_holds_exactly_one_word_of_its_pair():
    rng = random.Random(7)
    for _ in range(30):
        target = pick_pair(rng)
        assert target.focus in target.text.lower().replace(".", "").split()
        assert target.other not in target.text.lower().replace(".", "").split()


def test_both_words_of_each_pair_get_a_sentence():
    for a, b, sentence_a, sentence_b in _PAIRS:
        assert a in sentence_a.lower() and b in sentence_b.lower()
        assert a not in sentence_b.lower().split() and b not in sentence_a.lower().split()


def test_a_perfect_repetition():
    verdict = judge(Target("Could you tell me where the station is?"), "could you tell me where the station is")
    assert verdict.perfect and verdict.feedback == "Perfect!"


def test_an_imperfect_repetition_says_what_was_wrong_and_how_much_was_right():
    verdict = judge(Target("I like green apples"), "I like apples")
    assert not verdict.perfect
    assert verdict.feedback == "Missing: green. (75% of the words)"


def test_a_pair_is_correct_when_the_right_word_was_heard():
    target = Target("I can see a ship near the farm.", focus="ship", other="sheep")
    verdict = judge(target, "I can see a ship near the farm")
    assert verdict.perfect and "ship" in verdict.feedback


def test_a_pair_is_wrong_when_the_other_word_was_heard():
    target = Target("I can see a ship near the farm.", focus="ship", other="sheep")
    verdict = judge(target, "I can see a sheep near the farm")
    assert not verdict.perfect and "'sheep'" in verdict.feedback and "'ship'" in verdict.feedback


def test_a_pair_is_wrong_when_neither_word_was_heard():
    target = Target("I like to walk here.", focus="walk", other="work")
    verdict = judge(target, "I like to talk here")
    assert not verdict.perfect and verdict.feedback.startswith("I did not hear 'walk'")


def test_kinds_have_stable_values():
    assert [k.value for k in DrillKind] == ["shadow", "pairs", "dictation"]
