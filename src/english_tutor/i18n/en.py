"""English interface texts (the reference catalog; also the fallback)."""

from __future__ import annotations

from .en_settings import SETTINGS_STRINGS

STRINGS: dict[str, str] = {
    # Window chrome
    "app.title": "AI English Tutor - Virtual Assistant",
    "app.heading": "English Virtual Tutor",
    "tab.chat": "Chat",
    "tab.mistakes": "Mistakes",
    "hint.hold": "Hold '{key}' to speak, release to send",
    # Microphone, level, status, buttons
    "mic.label": "Select Microphone:",
    "mic.none": "None",
    "level.label": "Audio Level:",
    "button.end_session": "End session",
    "button.stop_practice": "Stop practice",
    "button.practice": "Practice",
    "tooltip.settings": "Settings ({shortcut})",
    "tooltip.end_session_disabled": "Available when Alex is idle",
    # Status chip (one per session state)
    "chip.loading": "Loading",
    "chip.idle": "Ready",
    "chip.recording": "Recording",
    "chip.transcribing": "Transcribing",
    "chip.thinking": "Thinking",
    "chip.speaking": "Speaking",
    "chip.reporting": "Reporting",
    # Status messages (see i18n.translate_status)
    "status.initializing": "Initializing...",
    "status.ready": "Ready",
    "status.ready_hold": "Ready: hold {key}",
    "status.practice_hold": "Practice: hold {key} to answer",
    "status.loading": "Loading speech model...",
    "status.listening": "Listening...",
    "status.transcribing": "Transcribing...",
    "status.thinking": "Thinking...",
    "status.speaking": "Speaking...",
    "status.preparing_practice": "Preparing practice...",
    "status.checking_answer": "Checking your answer...",
    "status.writing_feedback": "Writing feedback...",
    "status.too_short": "Too short or too quiet, try again",
    "status.not_caught": "Didn't catch that, try again",
    # Chat bubbles
    "chat.empty": "Hold {key} and speak to start the conversation.",
    "chat.you": "You: {text}",
    "chat.alex": "Alex: {text}",
    "chat.tip": 'Tip: "{original}"  ->  "{corrected}"',
    "practice.correct": "Correct!",
    "practice.retry": "Try again:",
    "practice.banner": 'Practicing: "{original}" -> "{corrected}"',
    # Mistakes tab
    "mistakes.empty": "No mistakes yet. Talk with Alex and they will appear here.",
    "mistakes.truncated": "Showing the {shown} most frequent of {total} mistakes.",
    "mistakes.stats": "x{count}   last seen {date}   practice {successes}/{attempts}",
    "severity.major": "MAJOR",
    "severity.minor": "MINOR",
    "restart.failed": (
        "The app could not restart itself. Your settings were saved; "
        "start it again with: python main.py"
    ),
}

STRINGS.update(SETTINGS_STRINGS)
