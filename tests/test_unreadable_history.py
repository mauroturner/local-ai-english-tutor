"""An unreadable history must never be overwritten by a later save."""

from __future__ import annotations

import pytest
from conftest import FakePhrases, FakeVocabularyStore, major

from english_tutor.adapters.json_mistake_store import JsonMistakeStore
from english_tutor.application.events import ErrorRaised
from english_tutor.domain.models import TutorReply
from english_tutor.domain.vocabulary import PhraseSuggestion
from english_tutor.ports import StartedFresh, StorageError


def test_a_read_error_keeps_the_file_untouched_for_the_whole_run(make_harness, fake_store):
    fake_store.load_error = StorageError("Could not read the mistake history: locked")
    fix = (major("I go", "I went"),)
    h = make_harness(["I go home", "I go out"], [TutorReply("a", fix), TutorReply("b", fix)], store=fake_store)
    h.say()
    h.say()
    assert fake_store.saves == []  # nothing was written over the unread data
    warnings = [e.message for e in h.of_type(ErrorRaised)]
    assert len([m for m in warnings if "locked" in m]) == 1  # told once, with the consequence
    assert "will not be saved" in warnings[-1] and "untouched" in warnings[-1]
    assert len(h.session.turns) == 2  # the conversation itself is unaffected


def test_a_file_set_aside_lets_a_new_history_start_and_save(make_harness, fake_store):
    fake_store.load_error = StartedFresh("History was unreadable; saved a copy as x and started a new one")
    fix = (major("I go", "I went"),)
    h = make_harness(["I go home"], [TutorReply("a", fix)], store=fake_store)
    h.say()
    assert len(fake_store.saves) == 1


def test_the_real_store_reports_a_set_aside_file_as_started_fresh(tmp_path):
    path = tmp_path / "mistakes.json"
    path.write_text("{ nope", encoding="utf-8")
    with pytest.raises(StartedFresh):
        JsonMistakeStore(path).load()


def test_the_real_store_reports_a_read_error_as_a_plain_storage_error(tmp_path, monkeypatch):
    from pathlib import Path

    path = tmp_path / "mistakes.json"
    path.write_text("{}", encoding="utf-8")

    def locked(self, *args, **kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "read_text", locked)
    with pytest.raises(StorageError) as caught:
        JsonMistakeStore(path).load()
    assert not isinstance(caught.value, StartedFresh)


def test_the_word_list_is_protected_the_same_way(make_harness):
    store = FakeVocabularyStore()
    store.load_error = StorageError("Could not read the word list: locked")
    h = make_harness(["hello"], [TutorReply("That sounds like a lot of fun!")], vocabulary=store,
                     phrases=FakePhrases([PhraseSuggestion("a lot of fun", "x", "y")]))
    h.say()
    h.session.save_phrase()
    assert store.saves == []
