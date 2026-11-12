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
    "setting.clear_logs.label": "Delete conversation logs",
    "setting.clear_logs.help": "Permanently deletes every saved conversation file. "
    "Your mistake history is kept.",
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
    # Restart banner
    "banner.restart": "Restart the app to apply: {names}",
    "banner.restart_now": "Restart now",
    "banner.later": "Later",
    "restart.confirm_title": "Restart now?",
    "restart.confirm_message": "The current conversation will end. Restart anyway?",
}
