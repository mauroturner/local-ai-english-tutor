"""Which rows the Settings content area shows (pure; no Tk root is created)."""

from __future__ import annotations

from english_tutor.i18n import en
from english_tutor.settings.registry import REGISTRY, Category, Control
from english_tutor.ui.services import ENABLED_ACTIONS
from english_tutor.ui.settings.pages import enabled_specs, match_counts, visible_result


def english(key: str) -> str:
    return en.STRINGS[key]


def keys(result) -> set[str]:
    return {spec.key for specs in result.values() for spec in specs}


def test_actions_that_do_not_exist_yet_are_hidden():
    shown = enabled_specs(REGISTRY, ENABLED_ACTIONS)
    action_keys = {s.key for s in shown if s.control is Control.ACTION}
    assert action_keys == set(ENABLED_ACTIONS)
    assert {s.key for s in shown if s.control is not Control.ACTION} == {
        s.key for s in REGISTRY if s.control is not Control.ACTION
    }


def test_without_a_query_only_the_selected_category_is_shown():
    result = visible_result("", Category.AUDIO, ENABLED_ACTIONS, english)
    assert list(result) == [Category.AUDIO]
    assert "tts_enabled" in keys(result)


def test_with_a_query_matches_from_every_category_are_shown():
    result = visible_result("folder", Category.GENERAL, ENABLED_ACTIONS, english)
    assert {Category.STORAGE, Category.ADVANCED} <= set(result)
    assert "export_report" not in keys(result)  # hidden action


def test_categories_left_empty_by_the_action_filter_disappear():
    result = visible_result("export", Category.GENERAL, set(), english)
    assert Category.STORAGE in result
    assert keys(result).isdisjoint({"export_report", "export_mistakes"})


def test_match_counts_cover_every_category():
    counts = match_counts("dark", ENABLED_ACTIONS, english)
    assert set(counts) == set(Category)
    assert counts[Category.APPEARANCE] >= 1
    assert counts[Category.STORAGE] == 0
    assert all(n == 0 for n in match_counts("zzzzzz", ENABLED_ACTIONS, english).values())


def test_connection_test_and_logs_folder_rows_are_enabled():
    assert {"test_connection", "open_logs_folder"} <= ENABLED_ACTIONS
