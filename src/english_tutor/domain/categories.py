"""The kinds of mistake the tutor labels, and how to count them."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any, Protocol, TypeVar

FLUENCY = "fluency"
"""Long pauses; assigned by the app, never by the model."""

OTHER = "other"

MODEL_CATEGORIES = (
    "verb_tense",
    "agreement",
    "articles",
    "prepositions",
    "word_order",
    "word_choice",
    "false_friend",
    "plural",
    "pronoun",
    OTHER,
)
"""What the model may answer with (the enum of the response schema)."""

ALL_CATEGORIES = (*MODEL_CATEGORIES, FLUENCY)


class _Categorized(Protocol):
    category: str | None


def parse_category(value: Any) -> str:
    """The category named by ``value``; anything unknown (or ``fluency``) becomes ``other``."""
    slug = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return slug if slug in MODEL_CATEGORIES else OTHER


def category_label(category: str) -> str:
    """Plain English name for reports, e.g. ``verb_tense`` -> ``verb tense``."""
    return category.replace("_", " ")


def count_categories(items: Iterable[_Categorized]) -> tuple[tuple[str, int], ...]:
    """How often each informative category occurs, most frequent first.

    Items without a category, ``other`` and ``fluency`` say nothing useful about
    what to study, so they are left out; ties are ordered by name.
    """
    counts = Counter(
        i.category for i in items if i.category and i.category not in (OTHER, FLUENCY)
    )
    return tuple(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def present_categories(items: Iterable[_Categorized]) -> tuple[str, ...]:
    """The categories that occur in ``items``, in the canonical order."""
    found = {i.category for i in items if i.category}
    return tuple(c for c in ALL_CATEGORIES if c in found)


_T = TypeVar("_T", bound=_Categorized)


def filter_by_category(items: Iterable[_T], category: str | None) -> tuple[_T, ...]:
    """The items of one category; ``None`` keeps everything."""
    return tuple(i for i in items if category is None or i.category == category)
