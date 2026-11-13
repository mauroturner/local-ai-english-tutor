"""Plain-text renderings shared by the UI and the conversation log."""

from __future__ import annotations

from collections.abc import Sequence

from .categories import category_label
from .fillers import filler_line
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


def vocabulary_line(report: SessionReport) -> str:
    """``Useful for this situation (not used yet): menu, order``; empty without a scenario."""
    if not report.unused_vocabulary:
        return ""
    return "Useful for this situation (not used yet): " + ", ".join(report.unused_vocabulary)


def uncertain_line(report: SessionReport) -> str:
    """``The recogniser was unsure about: very, world``; empty when it was sure of everything."""
    if not report.uncertain_words:
        return ""
    return "Check your pronunciation (the recogniser was unsure about): " + ", ".join(
        report.uncertain_words
    )


def vocabulary_summary(report: SessionReport) -> str:
    """``Vocabulary: 54 different words (12 new: ...). Used often: very (7)``; empty if no words."""
    if not report.vocabulary_unique:
        return ""
    text = f"Vocabulary: {report.vocabulary_unique} different words"
    if report.vocabulary_new:
        text += f" ({len(report.vocabulary_new)}+ new: {', '.join(report.vocabulary_new)})"
    if report.overused_words:
        text += ". Used often: " + ", ".join(f"{w} ({n})" for w, n in report.overused_words)
    return text


def format_report(report: SessionReport) -> str:
    """Render the end-of-session report as text."""
    lines = [f"SESSION REPORT ({report.turn_count} turns)", ""]
    lines += _format_errors("Major errors", report.major_errors)
    lines += _format_errors("Minor errors", report.minor_errors)
    if report.categories:
        lines.append(category_line(report))
    if report.unused_vocabulary:
        lines.append(vocabulary_line(report))
    if report.uncertain_words:
        lines.append(uncertain_line(report))
    if report.fillers:
        lines.append(filler_line(report.fillers))
    if report.vocabulary_unique:
        lines.append(vocabulary_summary(report))
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
