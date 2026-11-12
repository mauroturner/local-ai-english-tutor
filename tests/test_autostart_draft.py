"""The auto-start row's state, notes and wiring into the Settings flow (pure, no Tk)."""

from __future__ import annotations

import dataclasses
import re

from conftest import FakeWinreg

from english_tutor.adapters.windows_autostart import RUN_KEY, WindowsAutoStart
from english_tutor.application.preferences import SettingsService
from english_tutor.i18n import en, es, set_language, t
from english_tutor.ports import StorageError
from english_tutor.settings.autostart import AutostartDraft, relative_paths
from english_tutor.settings.model import UserSettings
from english_tutor.settings.registry import REGISTRY, TOGGLE_ACTIONS, Control
from english_tutor.ui.services import ENABLED_ACTIONS, UiServices

COMMAND = '"C:\\py\\pythonw.exe" "C:\\app\\main.py"'
STALE = '"C:\\old\\pythonw.exe" "C:\\old\\main.py"'
RUN = (FakeWinreg.HKEY_CURRENT_USER, RUN_KEY)


class MemoryStore:
    def __init__(self):
        self.data: dict = {}

    def load(self):
        return dict(self.data)

    def save(self, data):
        self.data = dict(data)


def setup_function(_):
    set_language("en")


def port(values=None, **kwargs) -> tuple[WindowsAutoStart, FakeWinreg]:
    registry = FakeWinreg({RUN: values} if values is not None else None, **kwargs)
    return WindowsAutoStart(registry, COMMAND), registry


# ----------------------------------------------------------------- registry/UI plumbing
def test_autostart_row_is_enabled_and_rendered_as_a_toggle():
    assert "autostart" in ENABLED_ACTIONS
    assert "autostart" in TOGGLE_ACTIONS
    spec = next(s for s in REGISTRY if s.key == "autostart")
    assert spec.control is Control.ACTION  # not a UserSettings field; nothing goes to settings.json
    assert UiServices.__dataclass_fields__["autostart"].default is None


def test_every_autostart_text_exists_in_both_languages_with_the_same_placeholders():
    keys = [k for k in en.STRINGS if k.startswith("autostart.")]
    assert keys
    for key in keys:
        assert key in es.STRINGS
        assert re.findall(r"\{(\w+)\}", en.STRINGS[key]) == re.findall(
            r"\{(\w+)\}", es.STRINGS[key]
        )


# ------------------------------------------------------------------------ real state
def test_the_row_reflects_the_real_registry_state_when_it_opens():
    draft = AutostartDraft.read(port({"EnglishTutor": COMMAND})[0])
    assert (draft.available, draft.enabled, draft.stale, draft.wanted) == (True, True, False, True)
    assert draft.dirty is False and draft.to_save() is None
    off = AutostartDraft.read(port({})[0])
    assert (off.enabled, off.wanted, off.dirty) == (False, False, False)


def test_toggling_makes_a_pending_change_that_save_applies():
    draft = AutostartDraft.read(port({})[0])
    draft.set(True)
    assert draft.dirty is True and draft.to_save() is True
    draft.set(False)
    assert draft.dirty is False and draft.to_save() is None
    on = AutostartDraft.read(port({"EnglishTutor": COMMAND})[0])
    on.set(False)
    assert on.to_save() is False


def test_a_stale_entry_shows_a_note_and_is_rewritten_on_save():
    auto, registry = port({"EnglishTutor": STALE})
    draft = AutostartDraft.read(auto)
    assert draft.stale and draft.wanted
    _, warning = draft.notes("", {})
    assert t("autostart.stale") in warning
    assert draft.dirty is True and draft.to_save() is True
    outcome = SettingsService(MemoryStore(), auto, {}).save(
        UserSettings(), UserSettings(), autostart=draft.to_save()
    )
    assert outcome.errors == ()
    assert registry.keys[RUN]["EnglishTutor"] == COMMAND


def test_unavailable_when_there_is_no_adapter_and_set_is_ignored():
    draft = AutostartDraft.read(None)
    assert draft.available is False
    assert draft.unavailable_text() == t("autostart.unavailable")
    draft.set(True)
    assert draft.dirty is False and draft.to_save() is None


def test_an_unreadable_registry_disables_the_row_with_the_reason():
    auto, _ = port({}, read_fail=PermissionError("no access"))
    draft = AutostartDraft.read(auto)
    assert "no access" in (draft.unavailable_text() or "")
    draft.set(True)
    assert draft.to_save() is None


# ---------------------------------------------------------------------------- notes
def test_enabling_warns_about_relative_paths_logon_and_model_loading():
    draft = AutostartDraft.read(port({})[0])
    assert draft.notes("", {}) == (None, None)  # nothing pending, nothing to warn about
    draft.set(True)
    error, warning = draft.notes("data", {"TUTOR_PIPER_EXE": "piper\\piper.exe"})
    assert error is None
    assert t("autostart.warn_startup") in warning
    assert "relative" in warning.lower() and "TUTOR_PIPER_EXE" in warning


def test_absolute_paths_cause_no_relative_warning():
    draft = AutostartDraft.read(port({})[0])
    draft.set(True)
    _, warning = draft.notes("D:\\tutor-data", {"TUTOR_PIPER_EXE": "C:\\piper\\piper.exe"})
    assert "relative" not in warning.lower()
    assert t("autostart.warn_startup") in warning


def test_relative_paths_helper_names_the_offending_settings():
    assert relative_paths("", {}) == ()
    assert relative_paths("D:\\data", {"TUTOR_PIPER_VOICE": "C:\\v.onnx"}) == ()
    names = relative_paths("data", {"TUTOR_PIPER_EXE": "piper.exe", "TUTOR_PIPER_VOICE": " "})
    assert len(names) == 2 and "TUTOR_PIPER_EXE" in names


def test_disabling_shows_no_enabling_warnings():
    draft = AutostartDraft.read(port({"EnglishTutor": COMMAND})[0])
    draft.set(False)
    assert draft.notes("data", {}) == (None, None)


# ----------------------------------------------------------------------- save flow
def test_enable_and_disable_through_the_service_use_the_registry():
    auto, registry = port({"Other": "keep"})
    service = SettingsService(MemoryStore(), auto, {})
    old = service.load().settings
    assert service.save(old, old, autostart=True).errors == ()
    assert registry.keys[RUN] == {"Other": "keep", "EnglishTutor": COMMAND}
    assert service.save(old, old, autostart=False).errors == ()
    assert registry.keys[RUN] == {"Other": "keep"}


def test_autostart_failure_is_reported_inline_and_writes_no_wrong_state():
    auto, registry = port({}, fail=PermissionError("denied"))
    service = SettingsService(MemoryStore(), auto, {})
    old = service.load().settings
    outcome = service.save(dataclasses.replace(old, language="es"), old, autostart=True)
    assert outcome.autostart_failed is True
    assert outcome.errors and "denied" in outcome.errors[0]
    assert registry.keys[RUN] == {}  # nothing half-written
    draft = AutostartDraft.read(auto)
    draft.set(True)
    draft.fail(outcome.errors[0])
    error, _ = draft.notes("", {})
    assert "denied" in error
    draft.set(False)  # the next edit clears the failure
    assert draft.notes("", {})[0] is None


def test_a_settings_store_failure_is_not_marked_as_an_autostart_failure():
    class Broken(MemoryStore):
        def save(self, data):
            raise StorageError("disk full")

    auto, registry = port({})
    outcome = SettingsService(Broken(), auto, {}).save(
        UserSettings(), UserSettings(), autostart=True
    )
    assert outcome.errors == ("disk full",) and outcome.autostart_failed is False
    assert registry.keys[RUN] == {}


def test_existing_save_behaviour_is_unchanged_and_never_touches_the_registry():
    store = MemoryStore()
    auto, registry = port({"EnglishTutor": COMMAND})
    service = SettingsService(store, auto, {})
    old = service.load().settings
    new = dataclasses.replace(old, language="es", ollama_model="qwen")
    outcome = service.save(new, old)
    assert store.data["language"] == "es" and "autostart" not in store.data
    assert set(outcome.restart_keys) == {"language", "ollama_model"}
    assert outcome.errors == () and outcome.autostart_failed is False
    assert registry.writes == [] and registry.keys[RUN] == {"EnglishTutor": COMMAND}


# ------------------------------------------------- Save when only auto-start fails
class _Footer:
    def __init__(self):
        self.status = None

    def set_status(self, text, error=False):
        self.status = (text, error)


def _commands_window(service, auto):
    from english_tutor.settings.draft import SettingsDraft
    from english_tutor.ui.settings.commands import SettingsCommands

    applied: list[UserSettings] = []

    class Window(SettingsCommands):
        closed = False

        def _preview(self, key=None):
            pass

        def _refresh_page(self):
            pass

        def _refresh_status(self):
            pass

        def _close(self):
            self.closed = True

    window = Window()
    window._services = UiServices(
        service, None, lambda _path: None, confirm=lambda *a, **k: True,
        on_applied=applied.append, autostart=auto,
    )  # fmt: skip
    loaded = service.load()
    window._effective = loaded.effective
    window._draft = SettingsDraft(loaded.settings, loaded.effective, loaded.locked)
    window._autostart = AutostartDraft.read(auto)
    window._folder_errors = {}
    window.footer = _Footer()
    return window, applied


def test_saved_settings_stay_saved_when_only_autostart_fails():
    auto, registry = port({}, fail=PermissionError("denied"))
    store = MemoryStore()
    window, applied = _commands_window(SettingsService(store, auto, {}), auto)
    window._draft.set("language", "es")
    window._autostart.set(True)

    assert window.save() is False  # the window stays open to show the failure
    assert store.data["language"] == "es"  # the settings file was written
    assert window._draft.dirty_keys == ()  # ...so they are no longer unsaved
    assert window._effective.language == "es"
    assert [s.language for s in applied] == ["es"]  # and applied like a normal save
    assert window.pending_changes == 1  # only the auto-start change is left
    assert window.footer.status[1] is True and "denied" in window.footer.status[0]
    assert window.closed is False and registry.keys[RUN] == {}
