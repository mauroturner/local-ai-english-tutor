"""Shortcut binder pure parts: which settings become bindings and how they change."""

from __future__ import annotations

import dataclasses

from english_tutor.settings.model import UserSettings
from english_tutor.ui.shortcut_binder import RebindPlan, plan_rebind, sequences_for


def with_shortcuts(**changes) -> UserSettings:
    return dataclasses.replace(UserSettings(), **changes)


def test_default_settings_give_four_bindings():
    assert sequences_for(UserSettings()) == {
        "end_session": "<Control-e>",
        "settings": "<Control-comma>",
        "chat_tab": "<Control-Key-1>",
        "mistakes_tab": "<Control-Key-2>",
    }


def test_blocking_conflicts_are_never_bound():
    settings = with_shortcuts(
        shortcut_end_session="Ctrl+C",  # reserved
        shortcut_settings="nonsense",  # invalid
        shortcut_chat_tab="Ctrl+2",  # duplicate with the Mistakes tab
        shortcut_mistakes_tab="Ctrl+2",
    )
    assert sequences_for(settings) == {}


def test_warnings_do_not_prevent_binding():
    settings = with_shortcuts(ptt_key="right ctrl")  # overlaps every Ctrl+ shortcut
    assert len(sequences_for(settings)) == 4


def test_unchanged_bindings_need_no_work():
    old = sequences_for(UserSettings())
    assert plan_rebind(old, dict(old)) == RebindPlan(unbind=(), bind={})


def test_first_binding_only_binds():
    new = sequences_for(UserSettings())
    assert plan_rebind({}, new) == RebindPlan(unbind=(), bind=new)


def test_changed_shortcut_unbinds_the_old_sequence_and_binds_the_new_one():
    old = sequences_for(UserSettings())
    new = {**old, "end_session": "<Control-k>"}
    assert plan_rebind(old, new) == RebindPlan(
        unbind=("<Control-e>",), bind={"end_session": "<Control-k>"}
    )


def test_a_shortcut_that_became_unusable_is_only_unbound():
    old = sequences_for(UserSettings())
    new = {k: v for k, v in old.items() if k != "settings"}
    assert plan_rebind(old, new) == RebindPlan(unbind=("<Control-comma>",), bind={})


def test_swapped_sequences_are_unbound_then_rebound():
    old = {"chat_tab": "<Control-Key-1>", "mistakes_tab": "<Control-Key-2>"}
    new = {"chat_tab": "<Control-Key-2>", "mistakes_tab": "<Control-Key-1>"}
    plan = plan_rebind(old, new)
    assert set(plan.unbind) == {"<Control-Key-1>", "<Control-Key-2>"}
    assert plan.bind == new
