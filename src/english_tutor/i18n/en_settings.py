"""English texts of the Settings window rows (see settings.registry)."""

from __future__ import annotations

SETTINGS_STRINGS: dict[str, str] = {
    # Sidebar sections
    "category.general": "General",
    "category.appearance": "Appearance",
    "category.audio": "Audio & notifications",
    "category.storage": "Storage",
    "category.shortcuts": "Shortcuts",
    "category.advanced": "Advanced",
    # Choice option names
    "option.language.en": "English",
    "option.language.es": "Español",
    "option.explain_language.en": "English",
    "option.explain_language.es": "Spanish",
    "option.level.A2": "A2 - Elementary",
    "option.level.B1": "B1 - Intermediate",
    "option.level.B2": "B2 - Upper intermediate",
    "option.level.C1": "C1 - Advanced",
    "option.learner_pronouns.he": "He/him",
    "option.learner_pronouns.she": "She/her",
    "option.learner_pronouns.they": "They/them",
    "option.appearance_mode.system": "System",
    "option.appearance_mode.light": "Light",
    "option.appearance_mode.dark": "Dark",
    "option.density.comfortable": "Comfortable",
    "option.density.compact": "Compact",
    "option.whisper_device.auto": "Automatic",
    "option.whisper_device.cuda": "GPU (CUDA)",
    "option.whisper_device.cpu": "CPU",
    # General
    "setting.language.label": "Interface language",
    "setting.language.help": "Language of menus and messages, and the date and time format. "
    "The tutor always speaks English.",
    "setting.learner_name.label": "Your name",
    "setting.learner_name.help": "The tutor calls you by this name now and then. "
    "Leave it empty to not be called by name.",
    "setting.learner_pronouns.label": "Your pronouns",
    "setting.learner_pronouns.help": "Used when the tutor refers to you, for example in "
    "the session report.",
    "setting.level.label": "English level",
    "setting.level.help": "Sets how simple the tutor's words are, how many corrections it gives "
    "per message and, at A2, how fast it speaks. Applies to the next message.",
    "setting.explain_language.label": "Explain corrections in",
    "setting.explain_language.help": "Language of the short explanation shown with each correction. "
    "The corrected sentence and everything the tutor says aloud stay in English.",
    "setting.track_pauses.label": "Track long pauses",
    "setting.track_pauses.help": "Notes where you stop for a long time in a sentence (1.2 s or "
    "more) and adds that phrase to Mistakes to practise saying it in one go. Also reports slow "
    "starts (3 s or more) in the session report. Pauses are never counted as errors.",
    "setting.suggest_natural.label": "Suggest more natural phrasing",
    "setting.suggest_natural.help": "When your sentence is correct but a native speaker would "
    "say it differently, shows a more natural version under the reply. It is never counted as a "
    "mistake.",
    "setting.daily_goal_minutes.label": "Daily goal",
    "setting.daily_goal_minutes.help": "Minutes of conversation to aim for each day, from 0 to "
    "60. The main window shows today's minutes and your streak of days in a row. 0 switches the "
    "goal off.",
    "setting.autostart.label": "Start with Windows",
    "setting.autostart.help": "Open the app automatically when you sign in.",
    # Appearance
    "setting.appearance_mode.label": "Theme",
    "setting.appearance_mode.help": "Light, dark, or the same as the operating system.",
    "setting.ui_scale.label": "Interface scale",
    "setting.ui_scale.help": "Makes everything larger or smaller. Applies immediately.",
    "setting.chat_font_size.label": "Chat font size",
    "setting.chat_font_size.help": "Size of the conversation text, from 10 to 22 points.",
    "setting.density.label": "Layout density",
    "setting.density.help": "Compact uses less space between elements.",
    # Audio and notifications
    "setting.tts_enabled.label": "Voice output",
    "setting.tts_enabled.help": "Read the tutor's replies aloud with Piper.",
    "setting.cue_record_start.label": "Sound when recording starts",
    "setting.cue_record_start.help": "Play a short beep when the microphone starts listening.",
    "setting.cue_record_stop.label": "Sound when recording stops",
    "setting.cue_record_stop.help": "Play a short beep when the recording ends.",
    "setting.cue_error.label": "Sound on errors",
    "setting.cue_error.help": "Play a low double beep when something goes wrong.",
    "setting.notify_report.label": "Desktop notification for the report",
    "setting.notify_report.help": "Show a notification when the end-of-session report is ready "
    "and the window is not in focus.",
    # Storage
    "setting.data_dir.label": "Data folder",
    "setting.data_dir.help": "Where conversations, mistakes and logs are stored. "
    "Existing data is not moved.",
    "setting.export_dir.label": "Export folder",
    "setting.export_dir.help": "Where exported reports and mistake lists are saved by default. "
    "Empty means Documents.",
    "setting.open_data_folder.label": "Open data folder",
    "setting.open_data_folder.help": "Show the folder with your conversations and mistakes "
    "in File Explorer.",
    "setting.export_report.label": "Export last report",
    "setting.export_report.help": "Save the most recent session report as a Markdown file.",
    "setting.export_mistakes.label": "Export mistakes",
    "setting.export_mistakes.help": "Save the mistake list as a CSV file.",
    "setting.export_anki.label": "Export for Anki",
    "setting.export_anki.help": "Saves your mistakes as flashcards you can import into Anki "
    "(front: what you said, back: the correction and the rule). Pauses are not included.",
    "export.anki_title": "Export mistakes for Anki",
    "setting.clear_logs.label": "Delete conversation logs",
    "setting.clear_logs.help": "Permanently deletes every saved conversation file. "
    "Your mistake history is kept.",
    "setting.clear_memory.label": "Delete session memory",
    "setting.clear_memory.help": "Permanently deletes the notes the tutor kept about what you "
    "talked about, so it forgets earlier sessions. Session numbers and charts stay.",
    "setting.session_memory.label": "Remember earlier sessions",
    "setting.session_memory.help": "At the end of a session the tutor writes a few short notes "
    "about what you shared (a trip, a job, plans) and the next conversation can ask about them. "
    "The notes stay on this computer in data/sessions.json.",
    "setting.clear_mistakes.label": "Delete mistake history",
    "setting.clear_mistakes.help": "Permanently deletes every recorded mistake and its "
    "practice statistics.",
    # Shortcuts
    "setting.ptt_key.label": "Push-to-talk key",
    "setting.ptt_key.help": "Hold this key to speak. Other applications still receive it.",
    "setting.shortcut_end_session.label": "End session",
    "setting.shortcut_end_session.help": "Finishes the conversation and writes the report.",
    "setting.shortcut_settings.label": "Open settings",
    "setting.shortcut_settings.help": "Opens this window.",
    "setting.shortcut_chat_tab.label": "Go to the Chat tab",
    "setting.shortcut_chat_tab.help": "Shows the conversation.",
    "setting.shortcut_mistakes_tab.label": "Go to the Mistakes tab",
    "setting.shortcut_mistakes_tab.help": "Shows your recurring mistakes.",
    "setting.shortcut_repeat.label": "Repeat the last reply",
    "setting.shortcut_repeat.help": "Says the tutor's last words again.",
    "setting.shortcut_repeat_slow.label": "Repeat the last reply slowly",
    "setting.shortcut_repeat_slow.help": "Says the tutor's last words again, more slowly.",
    # Advanced
    "setting.whisper_device.label": "Speech recognition device",
    "setting.whisper_device.help": "Automatic uses the GPU when available. "
    "The CPU is slower but always works.",
    "setting.whisper_model.label": "Speech recognition model",
    "setting.whisper_model.help": "Larger models are more accurate but slower and need "
    "more memory.",
    "setting.ollama_url.label": "Ollama server URL",
    "setting.ollama_url.help": "Address of the Ollama server.",
    "setting.ollama_model.label": "Ollama model",
    "setting.ollama_model.help": "Model used for replies and feedback. It must already be "
    "downloaded.",
    "setting.test_connection.label": "Test Ollama connection",
    "setting.test_connection.help": "Checks that the server answers and the model is installed.",
    "setting.log_level.label": "Log detail",
    "setting.log_level.help": "How much information is written to the log file.",
    "setting.open_logs_folder.label": "Open logs folder",
    "setting.open_logs_folder.help": "Show the application log files, useful for support.",
    "setting.restore_defaults.label": "Restore default settings",
    "setting.restore_defaults.help": "Resets every setting to its default value. "
    "Nothing is saved until you click Save.",
    # Settings window chrome
    "settings.title": "Settings",
    "settings.search_placeholder": "Search settings (Ctrl+F)",
    "settings.search_empty": "No settings match '{query}'",
    "settings.dirty": "● Unsaved changes ({count})",
    "settings.clean": "No changes",
    "settings.pill_restart": "Restart required",
    "settings.locked": "Set by {var}",
    "settings.confirm_discard_title": "Discard changes?",
    "settings.confirm_discard": "You have unsaved changes. Close without saving?",
    "settings.confirm_restore_title": "Restore defaults?",
    "settings.confirm_restore": "Every setting will go back to its default value. "
    "Nothing is saved until you click Save.",
    "settings.save_failed": "Could not save the settings: {error}",
    "settings.action_failed": "{error}",
    "button.save": "Save",
    "button.cancel": "Cancel",
    "button.restore_defaults": "Restore defaults",
    "button.browse": "Browse...",
    "button.open": "Open",
    "unit.points": "{value} pt",
    "unit.minutes": "{value} min",
    # Restart banner
    "banner.restart": "Restart the app to apply: {names}",
    "banner.restart_now": "Restart now",
    "banner.later": "Later",
    "restart.confirm_title": "Restart now?",
    "restart.confirm_message": "The current conversation will end. Restart anyway?",
    # Key capture and push-to-talk pause
    "settings.ptt_paused": "Push-to-talk is paused while Settings is open.",
    "button.change": "Change...",
    "capture.title_ptt": "Push-to-talk key",
    "capture.title_shortcut": "New shortcut",
    "capture.prompt_ptt": "Press the key you will hold to speak.",
    "capture.prompt_shortcut": "Press the new shortcut, for example Ctrl+K.",
    "capture.hint": "Esc cancels.",
    "capture.unsupported": "That key cannot be used here.",
    # Storage actions: export, delete, folders
    "button.export": "Export...",
    "button.delete": "Delete...",
    "settings.export_report_unavailable": "Available after you end a session and its report "
    "appears.",
    "export.report_title": "Export session report",
    "export.mistakes_title": "Export mistakes",
    "export.type_markdown": "Markdown document",
    "export.type_csv": "CSV spreadsheet",
    "export.done": "Saved to {path}",
    "export.failed": "Could not save the file: {error}",
    "export.no_mistakes": "There are no mistakes to export yet.",
    "export.no_report": "There is no report to export yet. End a session first.",
    "settings.clear_busy": "Alex is busy right now. Wait until the turn or practice is "
    "finished, then try again.",
    "settings.clear_logs_title": "Delete conversation logs?",
    "settings.clear_logs_message": "Every conversation log file (session-*.log) in this "
    "folder will be permanently deleted:\n{folder}\n\nYour mistake history, settings and "
    "application logs are not affected. This cannot be undone.",
    "settings.clear_memory_title": "Delete session memory?",
    "settings.clear_memory_message": "The notes of {count} earlier session(s) will be deleted "
    "permanently. This cannot be undone.",
    "settings.clear_mistakes_title": "Delete mistake history?",
    "settings.clear_mistakes_message": "All {count} recorded mistakes and their practice "
    "statistics will be permanently deleted. Conversation logs and settings are not affected. "
    "This cannot be undone.",
    "settings.folder_error": "This folder cannot be used: {error}",
    "autostart.unavailable": "Not available on this system.",
    "autostart.read_failed": "The current start-up setting could not be read: {error}",
    "autostart.change_failed": "Could not change the start-up setting: {error}",
    "autostart.name_data_dir": "the data folder",
    "autostart.stale": "The saved start-up entry points to a different location (the app or "
    "its Python environment may have moved). Save to update it.",
    "autostart.warn_relative": "Relative path in: {names}. Windows starts the app from "
    "another folder at sign-in, so use absolute paths or the app will not find its files.",
    "autostart.warn_startup": "At sign-in, Ollama may not be running yet and loading the "
    "speech model slows the first minutes. Connection problems are reported once the app "
    "is open.",
    "data.cleared_logs": "Deleted {count} conversation log file(s).",
    "data.cleared_memory": "Session memory deleted ({count} session(s) had notes).",
    "data.cleared_mistakes": "Mistake history deleted ({count} mistakes).",
    # Test connection
    "button.test": "Test",
    "connection.testing": "Testing the connection...",
    "connection.ok": "Connected: Ollama is running and the model {model} is installed.",
    "connection.model_missing": "Ollama is running, but the model {model} is not installed. "
    "Download it with: ollama pull {model}",
    "connection.unreachable": "Cannot reach Ollama at {url}. Start it with: ollama serve",
    "connection.timeout": "Ollama at {url} did not answer in time. Check that it is running.",
    "connection.bad_url": "That address is not valid: {detail}",
}
