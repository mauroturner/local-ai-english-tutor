"""Plain-text renderings shared by the UI and the conversation log."""

from __future__ import annotations

from collections.abc import Sequence

from .categories import category_label
from .hesitation import explanation
from .models import Correction, PracticeReply, SessionReport


def correction_text(correction: Correction) -> str:
    """One-line description, e.g. ``"I go" -> "I went" (Past tense.) [major]``."""
    return (
        f'"{correction.original}" -> "{correction.corrected}" '
        f"({correction.explanation}) [{correction.severity.value}]"
    )


def practice_speech(reply: PracticeReply) -> str:
    """Text read aloud for a practice turn: the feedback, then the next question."""
    return " ".join(part for part in (reply.feedback.strip(), reply.next_prompt.strip()) if part)


def _format_errors(title: str, errors: Sequence[Correction]) -> list[str]:
    if not errors:
        return [f"{title}: none"]
    lines = [f"{title}:"]
    lines += [f'  - "{c.original}" -> "{c.corrected}" ({c.explanation})' for c in errors]
    return lines


def pause_lines(report: SessionReport) -> list[str]:
    """Long pauses and slow starts (none of them errors); empty when there were none."""
    lines: list[str] = []
    if report.pauses:
        lines.append("Long pauses (practice these phrases):")
        lines += [f'  - "{p.marked}" ({explanation(p)})' for p in report.pauses]
    if report.slow_starts:
        lines.append("Slow starts:")
        lines += [f'  - {s:.1f} s to answer "{q}"' for q, s in report.slow_starts]
    return lines


def category_line(report: SessionReport, limit: int = 3) -> str:
    """``Most frequent: prepositions (4), verb tense (3)``; empty when nothing was labelled."""
    top = ", ".join(f"{category_label(c)} ({n})" for c, n in report.categories[:limit])
    return f"Most frequent: {top}" if top else ""


def format_report(report: SessionReport) -> str:
    """Render the end-of-session report as text."""
    lines = [f"SESSION REPORT ({report.turn_count} turns)", ""]
    lines += _format_errors("Major errors", report.major_errors)
    lines += _format_errors("Minor errors", report.minor_errors)
    if report.categories:
        lines.append(category_line(report))
    lines += pause_lines(report)
    lines.append("")
    feedback = report.feedback
    if feedback is not None:
        lines.append(f"Feedback: {feedback.summary}")
        lines += [f"  + {s}" for s in feedback.strengths]
        lines += [f"  > Focus on: {f}" for f in feedback.focus_areas]
    elif report.turn_count:
        lines.append(f"Feedback unavailable: {report.feedback_error or 'unknown error'}")
    else:
        lines.append("No turns were recorded in this session.")
    return "\n".join(lines)
