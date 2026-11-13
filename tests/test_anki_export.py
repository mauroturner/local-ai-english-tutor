"""Anki export: flashcards from the mistake list."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from english_tutor.domain.export import anki_csv, anki_filename
from english_tutor.domain.models import MistakeRecord, Severity

WHEN = datetime(2026, 11, 13, 10, 5, 9)


def record(**changes) -> MistakeRecord:
    base = dict(
        key="k", original="I go", corrected="I went", explanation="Use the past tense.",
        severity=Severity.MAJOR, count=1, first_seen=WHEN, last_seen=WHEN, examples=("I go home",),
        category="verb_tense",
    )
    base.update(changes)
    return MistakeRecord(**base)


def rows(text: str) -> list[list[str]]:
    body = [line for line in text.splitlines(keepends=True) if not line.startswith("#")]
    return list(csv.reader(io.StringIO("".join(body)), delimiter=";"))


def test_the_file_name():
    assert anki_filename(WHEN) == "anki-mistakes-20261113-100509.csv"


def test_anki_is_told_the_separator_html_and_the_tags_column():
    text = anki_csv([record()])
    assert text.startswith("#separator:semicolon\r\n#html:true\r\n#tags column:3\r\n")


def test_each_mistake_becomes_a_card_with_tags():
    assert rows(anki_csv([record()])) == [
        ["I go", "I went<br>Use the past tense.", "english-tutor verb_tense major"],
    ]


def test_a_card_without_category_or_explanation():
    (card,) = rows(anki_csv([record(category=None, explanation="", severity=Severity.MINOR)]))
    assert card == ["I go", "I went", "english-tutor minor"]


def test_pauses_are_not_cards():
    pause = record(original="how's … everything", corrected="how's everything",
                   severity=Severity.HESITATION)
    assert rows(anki_csv([pause])) == []


def test_html_in_the_text_is_escaped_and_separators_are_quoted():
    card = rows(anki_csv([record(original="a <b>; b", corrected='say "x" & y')]))[0]
    assert card[0] == "a &lt;b&gt;; b"
    assert card[1] == "say &quot;x&quot; &amp; y<br>Use the past tense."


def test_cells_cannot_start_a_spreadsheet_formula():
    card = rows(anki_csv([record(original="=SUM(A1)", corrected="+1")]))[0]
    assert card[0] == "'=SUM(A1)" and card[1].startswith("'+1")


def test_no_mistakes_gives_only_the_header():
    assert anki_csv([]) == "#separator:semicolon\r\n#html:true\r\n#tags column:3\r\n"


def test_the_export_action_exists_and_is_enabled():
    from english_tutor.settings.registry import ACTION_KEYS
    from english_tutor.ui.services import ENABLED_ACTIONS

    assert "export_anki" in ACTION_KEYS and "export_anki" in ENABLED_ACTIONS
