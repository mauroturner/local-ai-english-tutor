"""Building the content area of the Settings window from the registry."""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

import customtkinter as ctk

from ...i18n import t
from ...settings.registry import Category, Control, SearchResult, SettingSpec, by_category, search
from .. import theme
from .rows import Row

MakeRow = Callable[[Any, SettingSpec], Row]


def enabled_specs(
    specs: tuple[SettingSpec, ...], actions: Collection[str]
) -> tuple[SettingSpec, ...]:
    """``specs`` without the action rows that are not available yet."""
    return tuple(s for s in specs if s.control is not Control.ACTION or s.key in actions)


def visible_result(
    query: str, category: Category, actions: Collection[str], translate: Callable[[str], str]
) -> SearchResult:
    """What the content area shows: all matches while searching, else one category."""
    if query.strip():
        found = search(query, translate)
    else:
        found = {category: by_category(category)}
    result: SearchResult = {}
    for cat, specs in found.items():
        shown = enabled_specs(specs, actions)
        if shown:
            result[cat] = shown
    return result


def match_counts(
    query: str, actions: Collection[str], translate: Callable[[str], str]
) -> dict[Category, int]:
    """How many rows of each category match ``query`` (zero for categories without any)."""
    result = visible_result(query, Category.GENERAL, actions, translate)
    return {cat: len(result.get(cat, ())) for cat in Category}


def build_page(
    parent: Any, result: SearchResult, query: str, make_row: MakeRow
) -> dict[str, Row]:
    """Fill ``parent`` with headings and rows; returns the rows by setting key."""
    rows: dict[str, Row] = {}
    if not result:
        ctk.CTkLabel(
            parent, text=t("settings.search_empty", query=query.strip()),
            text_color=theme.MUTED_TEXT, font=theme.FONT_BODY, wraplength=480,
        ).pack(pady=theme.SPACE_XL)  # fmt: skip
        return rows
    for category, specs in result.items():
        ctk.CTkLabel(
            parent, text=t(f"category.{category.value}"), font=theme.FONT_HEADING,
            text_color=theme.TEXT, anchor="w",
        ).pack(fill="x", pady=(theme.SPACE_M, theme.SPACE_S))  # fmt: skip
        for spec in specs:
            row = make_row(parent, spec)
            row.pack(fill="x", pady=(0, theme.SPACE_S))
            rows[spec.key] = row
    return rows
