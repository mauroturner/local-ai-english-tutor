"""Word-by-word comparison for shadowing and dictation."""

from __future__ import annotations

from english_tutor.domain.shadowing import (
    Outcome,
    WordDiff,
    accuracy,
    compare,
    describe,
    is_perfect,
    words,
)


def outcomes(target, said):
    return [(d.expected, d.said, d.outcome.value) for d in compare(target, said)]


def test_identical_sentences_match_ignoring_case_and_punctuation():
    diffs = compare("How is your day going?", "how is your day going")
    assert is_perfect(diffs) and accuracy(diffs) == 1.0 and describe(diffs) == "Perfect!"


def test_a_missing_word():
    assert outcomes("I like green apples", "I like apples") == [
        ("i", "i", "ok"), ("like", "like", "ok"), ("green", None, "missing"),
        ("apples", "apples", "ok"),
    ]


def test_an_extra_word():
    assert [d.outcome for d in compare("I like apples", "I really like apples")] == [
        Outcome.OK, Outcome.EXTRA, Outcome.OK, Outcome.OK,
    ]


def test_a_changed_word():
    diffs = compare("The ship is big", "The sheep is big")
    assert WordDiff("ship", "sheep", Outcome.CHANGED) in diffs
    assert accuracy(diffs) == 0.75


def test_longer_replacements_pair_up_and_the_rest_is_missing_or_extra():
    diffs = compare("a b c d", "a x y")
    assert [(d.expected, d.said, d.outcome) for d in diffs] == [
        ("a", "a", Outcome.OK), ("b", "x", Outcome.CHANGED), ("c", "y", Outcome.CHANGED),
        ("d", None, Outcome.MISSING),
    ]
    assert [d.outcome for d in compare("a b", "a x y z")][-2:] == [Outcome.EXTRA, Outcome.EXTRA]


def test_contractions_match_their_long_form():
    assert is_perfect(compare("I don't know, it's late", "I do not know it is late"))
    assert words("They're here") == ["they", "are", "here"]


def test_nothing_said_means_every_word_is_missing():
    diffs = compare("good morning", "")
    assert [d.outcome for d in diffs] == [Outcome.MISSING, Outcome.MISSING]
    assert accuracy(diffs) == 0.0


def test_an_empty_target_has_nothing_to_miss():
    assert accuracy(compare("", "hello")) == 1.0
    assert not is_perfect(compare("", "hello"))


def test_the_description_lists_each_kind_of_difference():
    text = describe(compare("I like green apples a lot", "I liked apples very lot"))
    assert text == "Missing: green. Changed: 'liked' instead of 'like', 'very' instead of 'a'."
    assert describe(compare("one two", "one two three")) == "Extra: three."
