"""Text files the learner can export: the session report and the mistake list (pure)."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import datetime

from .formatting import category_line, vocabulary_line
from .hesitation import explanation
from .models import Correction, MistakeRecord, SessionReport

CSV_ENCODING = "utf-8-sig"
"""The byte-order mark lets Excel open the file as UTF-8."""

_CSV_HEADERS = (
    "severity", "original", "corrected", "explanation", "count", "first_seen", "last_seen",
    "practice_attempts", "practice_successes", "examples", "category",
)  # fmt: skip


def report_filename(when: datetime) -> str:
    """Suggested file name for an exported report."""
    return f"session-report-{when:%Y%m%d-%H%M%S}.md"


def mistakes_filename(when: datetime) -> str:
    """Suggested file name for the exported mistake list."""
    return f"mistakes-{when:%Y%m%d-%H%M%S}.csv"


def _error_lines(title: str, errors: Sequence[Correction]) -> list[str]:
    lines = [f"## {title}", ""]
    if not errors:
        return [*lines, "None.", ""]
    lines += [f'- "{c.original}" -> "{c.corrected}" ({c.explanation})' for c in errors]
    return [*lines, ""]


def _pause_lines(report: SessionReport) -> list[str]:
    lines: list[str] = []
    if report.pauses:
        lines += ["## Long pauses", ""]
        lines += [f'- "{p.marked}" ({explanation(p)})' for p in report.pauses]
        lines.append("")
    if report.slow_starts:
        lines += ["## Slow starts", ""]
        lines += [f'- {s:.1f} s to answer "{q}"' for q, s in report.slow_starts]
        lines.append("")
    return lines


def _feedback_lines(report: SessionReport) -> list[str]:
    feedback = report.feedback
    if feedback is None:
        if report.turn_count:
            return [f"Feedback unavailable: {report.feedback_error or 'unknown error'}", ""]
        return ["No turns were recorded in this session.", ""]
    lines = [feedback.summary, ""]
    if feedback.strengths:
        lines += ["### Strengths", "", *(f"- {s}" for s in feedback.strengths), ""]
    if feedback.focus_areas:
        lines += ["### Focus on", "", *(f"- {f}" for f in feedback.focus_areas), ""]
    return lines


def report_markdown(report: SessionReport, when: datetime) -> str:
    """Render ``report`` as a Markdown document exported at ``when``."""
    lines = [
        "# Session report",
        "",
        f"Exported {when:%Y-%m-%d %H:%M}. Turns: {report.turn_count}",
        "",
        *_error_lines("Major errors", report.major_errors),
        *_error_lines("Minor errors", report.minor_errors),
        *([category_line(report), ""] if report.categories else []),
        *([vocabulary_line(report), ""] if report.unused_vocabulary else []),
        *_pause_lines(report),
        "## Feedback",
        "",
        *_feedback_lines(report),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _text_cell(value: str) -> str:
    """Prefix ``'`` so a spreadsheet shows the text instead of running it as a formula.

    The text comes from speech transcription and the language model, so it must
    never be able to start a formula when the CSV is opened in Excel or similar.
    """
    return f"'{value}" if value.startswith(_FORMULA_STARTS) else value


def mistakes_csv(records: Sequence[MistakeRecord]) -> str:
    """Render the mistakes as CSV: English headers, ISO timestamps, examples joined by `` | ``."""
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(_CSV_HEADERS)
    for r in records:
        writer.writerow((
            r.severity.value, _text_cell(r.original), _text_cell(r.corrected),
            _text_cell(r.explanation), r.count,
            r.first_seen.isoformat(timespec="seconds"), r.last_seen.isoformat(timespec="seconds"),
            r.practice_attempts, r.practice_successes, _text_cell(" | ".join(r.examples)),
            r.category or "",
        ))  # fmt: skip
    return out.getvalue()
