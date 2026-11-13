# Security notes

## Everything runs locally

Speech recognition (faster-whisper), the language model (Ollama) and speech synthesis (Piper) all run on your machine. Microphone audio is kept in memory and passed to Whisper as an array; the app does not write it to disk. Transcripts are written to disk only in the conversation log described below, and the console log does not contain transcript text. The only network traffic the app itself triggers is:

- the one-time Whisper model download from Hugging Face on first run (performed by faster-whisper), and
- HTTP requests to the Ollama server at `TUTOR_OLLAMA_URL` (or the **Ollama server URL** setting), including the one made by **Test connection**.

The app has no accounts, no telemetry, no update check and no proxy support.

## Stored data is unencrypted

The app keeps your history on disk in plain text under `data\` (or `TUTOR_DATA_DIR`):

- `data\conversations\session-*.log` contains everything you said (the raw transcripts), the tutor's replies, the tips, the long pauses found in your speech, the session reports and the practice results.
- `data\mistakes.json` contains your recurring mistakes and long pauses, up to three example sentences of yours per item, and your practice scores. The tutor model also receives your name and pronouns from the settings.
- `data\sessions.json` contains one entry per session: numbers (date, duration, words, mistake and pause counts) and, unless **Remember earlier sessions** is off, a few short notes written by the tutor model about what you talked about (for example a trip or your job). They are sent back to the same local model at the start of later conversations and never leave the computer. It also lists, per session, the distinct content words you used (to find new words). Delete the notes with **Settings > Storage > Delete session memory**; the word lists and numbers are removed only by deleting `sessions.json`.
- `data\settings.json` contains your preferences and `data\logs\app.log` the application log (see [below](#settings-and-the-application-log)).
- Files you export (report as Markdown, mistakes as CSV) contain the same text and live wherever you saved them; the app does not track or clean them up.
- In the mistakes CSV, a text cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a leading `'`, so a spreadsheet shows it as text instead of running it as a formula (the text comes from transcription and the language model).

Neither file is encrypted or protected beyond normal Windows file permissions. Anyone who can read your user folder can read them. The `data/`, `logs/` and `*.log` paths are git-ignored, so they are not committed by accident.

**To wipe the history from the app**, use **Settings > Storage > Delete conversation logs / Delete mistake history** (see [What the app deletes](#what-the-app-deletes)). **To wipe everything, close the app and delete the `data` folder** (`Remove-Item -Recurse -Force data`). Deleting only `data\conversations` removes the logs; deleting only `data\mistakes.json` removes the mistake history. See [configuration.md](configuration.md#wiping-the-data).

**Do not point `TUTOR_DATA_DIR` at a synced cloud folder** (for example OneDrive, Dropbox or Google Drive) unless you accept that your transcripts are uploaded to that service. Note that a project folder placed under OneDrive's `Desktop` or `Documents` is synced as well, so the default `<project root>\data` can end up in the cloud in that case. Set `TUTOR_DATA_DIR` to a local, non-synced folder if that matters to you.

## Keep the Ollama URL on localhost

Your transcripts, the conversation history and the end-of-session text are sent to `TUTOR_OLLAMA_URL` as plain-text JSON over HTTP, with no authentication or encryption added by the app. The default is `http://localhost:11434`. Only point it at another host if you fully trust that host and the network path between you and it.

## `TUTOR_PIPER_EXE` is executed as-is

The file named by `TUTOR_PIPER_EXE` (or found by the [resolution order](configuration.md#piper-resolution-order), including `piper\piper.exe` in the repository and in the current directory) is started as a subprocess with an argument list (no shell) each time the tutor speaks. Only use a Piper binary you downloaded from a source you trust, and do not run the app from a directory whose `piper\piper.exe` you did not place there. Likewise, treat environment variables as trusted input: anyone who can set them for your session can choose which executable runs.

The text to be spoken is passed to Piper on standard input, with newlines replaced by spaces.

## Temporary audio

Synthesised speech is written to a temporary WAV file created with `tempfile.mkstemp` in the system temp folder. It is played and then deleted in a `finally` block, so it is removed even when playback or synthesis fails.

## Global keyboard hook

Push-to-talk uses the `keyboard` package, which installs a system-wide hook. The app only reacts to the configured key (the **Push-to-talk key** setting or `TUTOR_PTT_KEY`, default V) and does not store or log other key presses, but the hook is active while the app runs, including when other windows have focus. Some security software flags such hooks. While **Settings** is open the hook ignores key presses, so typing there starts no recording.

The key-capture dialog and the in-app shortcuts use ordinary Tk key events, which only exist while the app's own window has focus; no extra global hook is installed for them.

## Desktop notification (PowerShell toast)

When the end-of-session report is ready and the window is not focused, the app shows a Windows toast. To avoid a new dependency it starts `powershell.exe -NoProfile -NonInteractive -EncodedCommand <base64>` without a console window and with a 10 s timeout, from a background thread.

- The script is built from a fixed template. The only variable parts are the title and body, which are fixed application strings (`Your session report is ready`), not model output or transcripts. They are still escaped for XML and for a PowerShell single-quoted string, so they cannot break out of the script.
- `-EncodedCommand` passes the script as Base64 UTF-16, so nothing is parsed from a command line and no temporary script file is written.
- The script uses only the local Windows notification API. It makes **no network access** and runs in your user session without elevation.
- If PowerShell fails or times out, the app flashes its taskbar button instead. Turn the toast off with **Settings > Audio & notifications**.

## Start with Windows writes to the registry

Turning **Start with Windows** on writes one value; turning it off deletes that value and nothing else:

| Item | Value |
| --- | --- |
| Hive | `HKEY_CURRENT_USER` only (no administrator rights, nothing machine-wide) |
| Key | `Software\Microsoft\Windows\CurrentVersion\Run` |
| Value | `EnglishTutor` = `"<pythonw.exe>" "<project root>\main.py"` |

Both paths are quoted. Windows runs that command at every sign-in, so anyone who can edit `main.py` or the project folder controls what runs at logon; keep the folder writable only by you. How to remove the entry by hand: [configuration.md](configuration.md#start-with-windows).

## What the app deletes

The delete buttons in **Settings > Storage** ask for confirmation first and are refused while the tutor is busy:

| Button | Deletes | Never touches |
| --- | --- | --- |
| Delete conversation logs | Files named `session-*.log` in `<data folder>\conversations` | Other files and sub-folders, the mistake history, `settings.json`, `logs\app.log` |
| Delete mistake history | Empties `mistakes.json` (writes an empty list) | Conversation logs, settings |
| Delete session memory | Removes the notes from every entry of `sessions.json` | The session numbers, conversation logs, settings |

Deleted files are removed with the normal file API, not securely wiped. **Export** buttons write only where you point the save dialog, using a temporary file and a replace so a failed export never leaves a half-written file.

## Settings and the application log

`settings.json` stores your preferences (language, theme, keys, Ollama URL and model, folders). It never contains the value of a `TUTOR_*` variable that overrides a setting. `logs\app.log` holds application messages (start-up, warnings, errors, the data folder path); it does not contain transcript text. It rotates at 1 MB and keeps 3 older files. Both live in the git-ignored data folder; check the log before attaching it to a bug report, since it contains local paths.

## Test connection

**Test connection** sends one `GET <URL>/api/tags` with a 3 s timeout to the address currently in the form, from a background thread. The same rule applies as for `TUTOR_OLLAMA_URL`: a host other than localhost gets a warning, because your speech text would be sent there.

## Git hygiene

`.gitignore` excludes the Piper binaries and voices (`piper/`, `*.exe`, `*.dll`, `*.onnx`, `*.onnx.json`), virtual environments, `*.wav` files, `.env`, and the private learner data (`data/` with the settings, logs and history, `logs/`, `*.log`), so downloaded binaries and local secrets are not committed by accident.
