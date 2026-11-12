"""Pure correction rules."""

from __future__ import annotations

from conftest import major, minor

from english_tutor.domain.corrections import (
    compose_speech,
    dedupe,
    filter_corrections,
    is_cosmetic,
    normalize,
    pick_live,
    spoken_line,
)


def test_normalize_lowercases_and_strips_punctuation_keeping_apostrophes():
    assert normalize("  Hi,  Could you   hear me?! ") == "hi could you hear me"
    assert normalize("He don't") == "he don't"


def test_cosmetic_correction_detected():
    assert is_cosmetic(major("hi", "Hi,"))
    assert not is_cosmetic(major("I go", "I went"))


def test_filter_drops_cosmetic_empty_and_invented():
    transcript = "hi yesterday I go to the park"
    kept = filter_corrections(
        transcript,
        [
            major("hi", "Hi,"),
            major("", "x"),
            major("I go", ""),
            major("she goes", "she went"),
            major("I go", "I went"),
        ],
    )
    assert [c.original for c in kept] == ["I go"]


def test_filter_matches_ignoring_case_and_punctuation():
    kept = filter_corrections("Yesterday, I go.", [major("yesterday i go", "yesterday i went")])
    assert len(kept) == 1


def test_filter_requires_whole_words():
    assert filter_corrections("I gone home", [major("I go", "I went")]) == ()


def test_pick_live_first_major_and_rest():
    a, b, c = minor("a x", "a"), major("b x", "b"), major("c x", "c")
    live, rest = pick_live([a, b, c])
    assert live == b
    assert rest == (a, c)


def test_pick_live_none_without_major():
    a = minor("a x", "a")
    assert pick_live([a]) == (None, (a,))
    assert pick_live([]) == (None, ())


def test_dedupe_keeps_first_occurrence():
    a = major("I go", "I went")
    dup = major("i go", "I went", "other text")
    assert dedupe([a, dup, minor("x y", "x")]) == (a, minor("x y", "x"))


def test_spoken_line():
    assert spoken_line(major("I go", "I went")) == "Quick tip: instead of 'I go', say 'I went'."


def test_compose_speech_puts_the_tip_before_the_reply():
    live = major("I go", "I went")
    assert compose_speech("Where?", live) == f"{spoken_line(live)} Where?"


def test_compose_speech_without_a_live_correction_is_the_reply():
    assert compose_speech("Where?", None) == "Where?"
