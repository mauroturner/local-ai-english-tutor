"""SettingsService: load with warnings/locks, save without leaking env values."""

from __future__ import annotations

import dataclasses

from english_tutor.application.preferences import SettingsService
from english_tutor.ports import StorageError
from english_tutor.settings.model import UserSettings


class MemoryStore:
    def __init__(self, data=None, load_error=None, save_error=None):
        self.data = dict(data or {})
        self.load_error = load_error
        self.save_error = save_error

    def load(self):
        if self.load_error:
            raise self.load_error
        return dict(self.data)

    def save(self, data):
        if self.save_error:
            raise self.save_error
        self.data = dict(data)


class FakeAutoStart:
    def __init__(self, enabled=False, stale=False, fail=False):
        self.enabled, self.stale, self.fail = enabled, stale, fail
        self.calls: list[str] = []

    def is_enabled(self):
        return self.enabled

    def is_stale(self):
        return self.stale

    def enable(self):
        if self.fail:
            raise StorageError("registry locked")
        self.calls.append("enable")
        self.enabled, self.stale = True, False

    def disable(self):
        self.calls.append("disable")
        self.enabled = False


def test_load_defaults_when_the_file_is_missing():
    loaded = SettingsService(MemoryStore(), None, {}).load()
    assert loaded.settings == UserSettings()
    assert loaded.warnings == ()
    assert loaded.locked == frozenset()


def test_load_reports_invalid_fields_and_keeps_the_rest():
    store = MemoryStore({"language": "es", "chat_font_size": 99})
    loaded = SettingsService(store, None, {}).load()
    assert loaded.settings.language == "es"
    assert loaded.settings.chat_font_size == 13
    assert len(loaded.warnings) == 1 and "chat_font_size" in loaded.warnings[0]


def test_load_survives_a_corrupt_file_with_a_warning():
    store = MemoryStore(load_error=StorageError("Settings were unreadable; saved a copy"))
    loaded = SettingsService(store, None, {}).load()
    assert loaded.settings == UserSettings()
    assert loaded.warnings == ("Settings were unreadable; saved a copy",)


def test_load_marks_env_locked_fields_but_keeps_file_values():
    store = MemoryStore({"ptt_key": "f9"})
    loaded = SettingsService(store, None, {"TUTOR_PTT_KEY": "right ctrl"}).load()
    assert loaded.locked == frozenset({"ptt_key"})
    assert loaded.settings.ptt_key == "f9"


def test_save_writes_json_and_reports_restart_keys_in_field_order():
    store = MemoryStore()
    service = SettingsService(store, None, {})
    old = service.load().settings
    new = dataclasses.replace(old, language="es", appearance_mode="dark", ptt_key="f9")
    outcome = service.save(new, old)
    assert outcome.errors == ()
    assert outcome.restart_keys == ("language", "ptt_key")
    assert store.data["appearance_mode"] == "dark"
    assert store.data["language"] == "es"


def test_save_without_changes_has_no_restart_keys():
    service = SettingsService(MemoryStore(), None, {})
    old = service.load().settings
    assert service.save(old, old).restart_keys == ()


def test_locked_fields_keep_the_stored_value_and_env_values_are_never_written():
    store = MemoryStore({"ptt_key": "f9"})
    service = SettingsService(store, None, {"TUTOR_PTT_KEY": "right ctrl"})
    old = service.load().settings
    effective = dataclasses.replace(old, ptt_key="right ctrl", language="es")
    outcome = service.save(effective, effective)
    assert store.data["ptt_key"] == "f9"
    assert store.data["language"] == "es"
    assert "right ctrl" not in store.data.values()
    assert "ptt_key" not in outcome.restart_keys


def test_locked_field_with_no_stored_value_is_written_as_the_default():
    store = MemoryStore()
    service = SettingsService(store, None, {"TUTOR_OLLAMA_MODEL": "qwen"})
    old = service.load().settings
    service.save(dataclasses.replace(old, ollama_model="qwen"), old)
    assert store.data["ollama_model"] == UserSettings().ollama_model


def test_store_failure_is_reported_and_autostart_untouched():
    auto = FakeAutoStart()
    service = SettingsService(MemoryStore(save_error=StorageError("disk full")), auto, {})
    old = service.load().settings
    outcome = service.save(dataclasses.replace(old, language="es"), old, autostart=True)
    assert outcome.errors == ("disk full",)
    assert auto.calls == []


def test_autostart_is_toggled_only_when_it_differs():
    auto = FakeAutoStart(enabled=False)
    service = SettingsService(MemoryStore(), auto, {})
    old = service.load().settings
    service.save(old, old, autostart=True)
    assert auto.calls == ["enable"]
    service.save(old, old, autostart=True)
    assert auto.calls == ["enable"]
    service.save(old, old, autostart=False)
    assert auto.calls == ["enable", "disable"]
    service.save(old, old)
    assert auto.calls == ["enable", "disable"]


def test_stale_autostart_entry_is_rewritten_on_save():
    auto = FakeAutoStart(enabled=True, stale=True)
    service = SettingsService(MemoryStore(), auto, {})
    old = service.load().settings
    service.save(old, old, autostart=True)
    assert auto.calls == ["enable"]


def test_autostart_failure_is_an_error_but_settings_are_saved():
    store = MemoryStore()
    service = SettingsService(store, FakeAutoStart(fail=True), {})
    old = service.load().settings
    outcome = service.save(dataclasses.replace(old, language="es"), old, autostart=True)
    assert outcome.errors == ("registry locked",)
    assert store.data["language"] == "es"


def test_autostart_request_without_an_adapter_is_ignored():
    service = SettingsService(MemoryStore(), None, {})
    old = service.load().settings
    assert service.save(old, old, autostart=True).errors == ()


def test_load_reports_the_effective_settings_with_env_values_applied():
    store = MemoryStore({"ptt_key": "f9", "language": "es"})
    env = {"TUTOR_PTT_KEY": "right ctrl", "TUTOR_TTS": "0", "TUTOR_LOG_LEVEL": "debug"}
    loaded = SettingsService(store, None, env).load()
    assert loaded.settings.ptt_key == "f9"
    assert loaded.effective.ptt_key == "right ctrl"
    assert loaded.effective.tts_enabled is False
    assert loaded.effective.log_level == "DEBUG"
    assert loaded.effective.language == "es"


def test_effective_ignores_an_env_value_the_model_rejects():
    store = MemoryStore({"ollama_url": "http://h:1"})
    loaded = SettingsService(store, None, {"TUTOR_OLLAMA_URL": "not a url"}).load()
    assert loaded.effective.ollama_url == "http://h:1"
