# Configuration

All settings are read once at start-up (`config.load_config`) from the defaults, the [settings file](#settings-file) and environment variables, in that order of increasing priority. Most people change settings in the [Settings window](#settings-window); the variables below are for power users, scripts and tests. Every variable is optional. An empty or whitespace-only value counts as "not set" and the default is used.

If a value is invalid the app prints `Configuration error: <message>` to standard error and exits with code `2` before opening a window. The message names the variable, for example `TUTOR_HISTORY_EXCHANGES must be an integer, got 'abc'` or `TUTOR_OLLAMA_TIMEOUT must be greater than 0, got 0.0`.

## Variables

| Variable | Type | Default | Effect |
| --- | --- | --- | --- |
| `TUTOR_OLLAMA_URL` | string | `http://localhost:11434` | Base URL of the Ollama server. A trailing `/` is removed. See [security-notes.md](security-notes.md) |
| `TUTOR_OLLAMA_MODEL` | string | `llama3:8b-instruct-q4_K_M` | Model used for replies and feedback. It must already be pulled; see [tutor-behavior.md](tutor-behavior.md#using-a-bigger-model) |
| `TUTOR_OLLAMA_TIMEOUT` | float, finite and > 0 (seconds) | `120` | Read timeout for `/api/chat` calls. The connect timeout is fixed at 5 s. On expiry the app shows `Ollama timed out after <n>s` |
| `TUTOR_LLM_TEMPERATURE` | float, finite and >= 0 | `0.5` | Sampling temperature sent to Ollama. There is no upper bound |
| `TUTOR_HISTORY_EXCHANGES` | integer >= 0 | `6` | How many learner/tutor exchanges are sent back to the model as memory. `0` disables memory. Negative values are rejected. Does not affect practice mode, which has its own memory |
| `TUTOR_WHISPER_MODEL` | string | `large-v3` | faster-whisper model name or path. Downloaded on first use if it is a model name |
| `TUTOR_WHISPER_DEVICE` | string | `auto` | `auto` and `cuda` try the GPU first and fall back to CPU if loading or the warm-up decode fails. Any other value (use `cpu`) loads on the CPU directly. The value is lower-cased; it is not validated |
| `TUTOR_WHISPER_COMPUTE_TYPE` | string | `float16` | Compute type for the GPU attempt |
| `TUTOR_WHISPER_CPU_COMPUTE_TYPE` | string | `int8` | Compute type for the CPU (fallback or `cpu` device) |
| `TUTOR_WHISPER_BEAM_SIZE` | integer >= 1 | `5` | Beam size passed to Whisper |
| `TUTOR_TTS` | boolean | `1` | Voice output. Accepted: `1`, `true`, `yes`, `on` / `0`, `false`, `no`, `off` (case-insensitive). When off, the app is text-only and logs `Voice output disabled (TUTOR_TTS=0).` |
| `TUTOR_PIPER_EXE` | path | auto-detected | Path to `piper.exe`. See [Piper resolution order](#piper-resolution-order) |
| `TUTOR_PIPER_VOICE` | path | `<folder of piper.exe>\voices\en_US-lessac-medium.onnx` | Voice model. A file with the same name plus `.json` (for example `en_US-lessac-medium.onnx.json`) must sit next to it |
| `TUTOR_PTT_KEY` | string | `v` | Push-to-talk key, as a key name understood by the `keyboard` package. Shown capitalised (`V`, `Right Ctrl`) in the window's hold hint. See [Push-to-talk key](#push-to-talk-key) |
| `TUTOR_DATA_DIR` | path | `<project root>\data` | Folder for the conversation logs and the mistake history. A relative path is relative to the working directory. See [Local data](#local-data) |
| `TUTOR_LOG_LEVEL` | string | `INFO` | Python logging level name (`DEBUG`, `INFO`, `WARNING`, ...). Upper-cased; an unknown name falls back to `INFO`. Logs go to the console and to [`logs\app.log`](#application-log) |
| `TUTOR_SETTINGS_FILE` | path | `<data folder>\settings.json` | Location of the settings file. See [Settings file](#settings-file) |

Notes:

- Numbers are parsed with Python's `int()` / `float()`. Ranges are enforced for the four numeric variables above; `nan` and `inf` are rejected for the float ones. Error texts: `must be greater than 0`, `must be 0 or greater`, `must be 1 or greater`.
- Use **absolute paths** for `TUTOR_PIPER_EXE` and `TUTOR_PIPER_VOICE`. Availability is checked against the app's working directory, whereas Piper itself is started with the folder of `piper.exe` as its working directory and receives the voice path unchanged.

## Settings file

User settings are saved in `settings.json`. Environment variables keep working and always win, so the effective value of each setting is decided in this order (later wins):

1. built-in default
2. `settings.json`
3. the `TUTOR_*` variable, when it is set and not blank

**Location.** `TUTOR_SETTINGS_FILE` if set, otherwise `settings.json` inside the data folder (`TUTOR_DATA_DIR`, default `<project root>\data`, git-ignored). The `data_dir` setting inside the file never moves the file itself; it only changes where conversations, mistakes and logs go.

**Format.** Versioned JSON, written atomically (temporary file, flush, `os.replace`), so a failed save keeps the previous file:

```json
{
  "version": 1,
  "settings": {
    "language": "en", "learner_name": "Mauro", "learner_pronouns": "he", "track_pauses": true, "suggest_natural": true,
    "appearance_mode": "system", "ui_scale": 1.0, "chat_font_size": 13,
    "density": "comfortable", "tts_enabled": true,
    "cue_record_start": true, "cue_record_stop": true, "cue_error": true,
    "notify_report": true, "data_dir": "", "export_dir": "", "ptt_key": "v",
    "shortcut_end_session": "Ctrl+E", "shortcut_settings": "Ctrl+,",
    "shortcut_chat_tab": "Ctrl+1", "shortcut_mistakes_tab": "Ctrl+2",
    "whisper_device": "auto", "whisper_model": "large-v3",
    "ollama_url": "http://localhost:11434", "ollama_model": "llama3:8b-instruct-q4_K_M",
    "log_level": "INFO"
  }
}
```

Missing keys use their default and unknown keys are ignored. A value that is invalid (wrong type, out of range, not one of the allowed choices, a bad Ollama URL) is replaced by its default **on its own**, the other settings are kept, and the app shows one chat notice per ignored value, for example `Ignored invalid setting: chat_font_size must be between 10 and 22, got 99; using 13.`

**Environment overrides.** Settings that have a variable (`tts_enabled` -> `TUTOR_TTS`, `data_dir` -> `TUTOR_DATA_DIR`, `ptt_key` -> `TUTOR_PTT_KEY`, `whisper_device`, `whisper_model`, `ollama_url`, `ollama_model`, `log_level` -> `TUTOR_WHISPER_DEVICE`, `TUTOR_WHISPER_MODEL`, `TUTOR_OLLAMA_URL`, `TUTOR_OLLAMA_MODEL`, `TUTOR_LOG_LEVEL`) are *locked* while that variable is set. A locked setting keeps the value stored in the file; the variable's value is never written to `settings.json`.

**Corrupt or unsupported file.** If the file is not valid JSON, has the wrong structure or a `version` other than 1, it is renamed to `settings.json.corrupt-YYYYmmdd-HHMMSS`, the app starts with the defaults and shows `Settings were unreadable; saved a copy as <name> and started with defaults`. If the rename fails, settings are read-only for that run and nothing is overwritten.

## Settings window

Open it with the gear button in the main window or **Ctrl+,**. Edits stay in a draft until you click **Save**.

| Feature | Behaviour |
| --- | --- |
| Sidebar | Six categories: General, Appearance, Audio & notifications, Storage, Shortcuts, Advanced. **Ctrl+PageUp** / **Ctrl+PageDown** move between them |
| Search | Box above the categories (**Ctrl+F**). Ignores case and accents and looks at the names, descriptions and keywords, in the current language and in English. Results are grouped by category with a match count; **Esc** clears the box, **Enter** jumps to the first result |
| Unsaved changes | The footer shows `● Unsaved changes (n)` and the title gets a dot. **Save** (**Ctrl+S**) is disabled when nothing changed or a field has an error. **Cancel**, **Esc** or closing the window asks `Discard changes?` when something is pending |
| Preview | Only the appearance mode and the chat font size preview while you edit; **Cancel** puts them back. Everything else is applied on **Save** |
| Restart required | Rows with an amber `Restart required` pill take effect after a restart. After **Save** a banner lists them with **Restart now** (asks first if the conversation has turns) and **Later** |
| Locked by environment | A setting whose `TUTOR_*` variable is set shows `Set by TUTOR_...` and is disabled. See [Settings file](#settings-file) |
| Restore defaults | Asks for confirmation, resets the draft (locked settings are kept) and waits for **Save** |
| Resizable | Default 860 x 600, minimum 720 x 480. The content column is capped at 640 px and centred, so wide windows stay readable |
| Push-to-talk | Paused while Settings is open (the window says so), because typing there would otherwise start recordings |

### General

| Setting | Values (default) | Applies | Notes |
| --- | --- | --- | --- |
| Interface language | `en`, `es` (`en`) | Restart | Buttons, labels, status messages and dates in the Mistakes tab (`Nov 12, 2026` / `12 nov 2026`). The tutor, corrections, reports and conversation logs stay English |
| Your name | text, up to 40 characters (`Mauro`) | Save | The tutor uses it now and then. Leave it empty to not be called by name. Quotes, braces, angle brackets, backslashes, backticks and control characters are refused |
| Your pronouns | `he` (he/him), `she` (she/her), `they` (they/them) (`he`) | Save | Used when the tutor refers to you in the third person, for example in the report |
| Track long pauses | on / off (on) | Save | Adds pauses of 1.2 s or more inside a sentence to the Mistakes tab and lists slow starts (3 s or more) in the report; never counted as errors. See [Long pauses](tutor-behavior.md#long-pauses) |
| Suggest more natural phrasing | on / off (on) | Save | When a sentence has no error but a native speaker would say it differently, shows `More natural: "..."` under the reply. Never a mistake, never spoken, never stored in the history; see [Natural phrasing](tutor-behavior.md#natural-phrasing) |
| Start with Windows | on / off (off) | Save | Not stored in `settings.json`; see [Start with Windows](#start-with-windows) |

### Appearance

| Setting | Values (default) | Applies | Notes |
| --- | --- | --- | --- |
| Theme | `system`, `light`, `dark` (`system`) | Live | `system` follows the Windows app mode |
| Interface scale | 0.8, 0.9, 1.0, 1.1, 1.25, 1.5 (1.0) | Live | Scales every widget |
| Chat font size | 10 to 22 (13) | Live | Chat bubbles only |
| Layout density | `comfortable`, `compact` (`comfortable`) | Restart | Spacing between elements |

### Audio and notifications

| Setting | Default | Applies | Notes |
| --- | --- | --- | --- |
| Voice output (`TUTOR_TTS`) | on | Restart | Off means text-only replies |
| Sound when recording starts / stops, sound on errors | on | Live | Three short beeps (start 880 Hz, stop 660 Hz, error 2 x 330 Hz) on their own audio stream, so they never cut off the tutor's voice. The error beep is silent while loading or speaking and plays at most once every 2 s. Transcripts are never touched |
| Desktop notification for the report | on | Live | A Windows toast `Your session report is ready` when the report arrives while the app window is not focused. Windows **Focus Assist / Do not disturb** may hide it; if the toast fails, the taskbar button flashes instead |

### Storage

| Setting | Default | Applies | Notes |
| --- | --- | --- | --- |
| Data folder (`TUTOR_DATA_DIR`) | empty = `<project root>\data` | Restart | Where conversations, mistakes and logs go. **Existing files are not moved**; the app just starts using the new folder. `settings.json` never moves. On **Save** the folder is created and a write test runs; failures appear under the row |
| Export folder | empty = `Documents` | Live | Where the save dialogs start |

| Action | What it does |
| --- | --- |
| Open data folder | Opens the folder in Explorer (created if missing) |
| Export last report | Saves the last report as Markdown (`session-report-YYYYmmdd-HHMMSS.md`). Disabled until a session has ended |
| Export mistakes | Saves the whole mistake list as CSV (`mistakes-YYYYmmdd-HHMMSS.csv`): UTF-8 with BOM so Excel opens it correctly, English headers, ISO dates, examples joined with ` \| `, and a last `category` column (empty when unknown) |
| Delete conversation logs | After confirmation deletes only `session-*.log` in `<data folder>\conversations` |
| Delete mistake history | After confirmation empties the mistake history and its practice scores |

Both delete actions are refused while the tutor is busy or a practice drill is running, and cannot be undone. Settings and the application log are never touched. Files are written atomically (temporary file, then replace).

### Shortcuts

| Setting | Default | Notes |
| --- | --- | --- |
| Push-to-talk key (`TUTOR_PTT_KEY`) | `v` | Restart. Global: works with other windows focused. See [Push-to-talk key](#push-to-talk-key) |
| End session | `Ctrl+E` | In-app, live |
| Open settings | `Ctrl+,` | In-app, live |
| Go to the Chat tab / Mistakes tab | `Ctrl+1` / `Ctrl+2` | In-app, live |

Click **Change...** and press the new key in the capture dialog (**Esc** cancels). In-app shortcuts are bound to the main window only, so they work when it is focused. Conflicts are checked as you edit:

| Kind | Result |
| --- | --- |
| Invalid text, duplicate of another action, no Ctrl/Alt (bare F-keys are allowed), reserved (`Ctrl+C/V/X/A/Z/Y/F/S`, `Alt+F4`) | Blocks **Save** |
| Overlap with the push-to-talk key (for example PTT `right ctrl` and any `Ctrl+` shortcut) | Warning only |

### Advanced

| Setting | Default | Applies | Notes |
| --- | --- | --- | --- |
| Speech recognition device (`TUTOR_WHISPER_DEVICE`) | `auto` | Restart | `auto`, `cuda`, `cpu` |
| Speech recognition model (`TUTOR_WHISPER_MODEL`) | `large-v3` | Restart | Pick from the list or type any model name or path |
| Ollama server URL (`TUTOR_OLLAMA_URL`) | `http://localhost:11434` | Restart | Must be `http` or `https` with a host and no query. A host other than localhost shows a warning |
| Ollama model (`TUTOR_OLLAMA_MODEL`) | `llama3:8b-instruct-q4_K_M` | Restart | Must already be pulled |
| Log detail (`TUTOR_LOG_LEVEL`) | `INFO` | Live | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

| Action | What it does |
| --- | --- |
| Test Ollama connection | Checks the URL and model **currently in the form**, even before you save, with a 3 s timeout, without freezing the window. Result under the row: connected and model installed; server up but model missing (run `ollama pull <model>`); server not reachable (`ollama serve`); no answer in time; invalid address |
| Open logs folder | Opens `<data folder>\logs` (created if missing); attach the files when asking for support |
| Restore default settings | See the table above |

### Start with Windows

The switch writes one value to the **current user's** registry, no administrator rights needed:

| Item | Value |
| --- | --- |
| Key | `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` |
| Value name | `EnglishTutor` |
| Value data | `"<folder of python.exe>\pythonw.exe" "<project root>\main.py"` (`pythonw.exe` when it exists, so no console window opens) |

The switch shows the real registry state each time Settings opens. If the entry points to an old location (you moved the project or its Python environment) the row says so and **Save** rewrites it.

**Remove it by hand:** turn the switch off and **Save**, or run `reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v EnglishTutor /f`, or disable the entry in Task Manager > Startup apps.

**Caveats.**

- Windows starts the app from another working directory, so a **relative** `TUTOR_DATA_DIR`, `TUTOR_PIPER_EXE` or `TUTOR_PIPER_VOICE` will not be found. The row warns about it; use absolute paths.
- Loading the Whisper model slows the first minutes after sign-in.
- Ollama may not be running yet at sign-in; the connection is checked once the app is open, and you can use **Test connection** later.
- The entry runs the project's `main.py` from where it is now. If you move or delete the folder, the entry breaks until you update or remove it.

### Application log

The app writes `<data folder>\logs\app.log` (UTF-8) at the level chosen in **Log detail**; the console shows the same records when there is one. The file rotates at **1 MB** and keeps **3** older files (`app.log.1` to `app.log.3`), so the logs never grow without bound. If the logs folder cannot be created, the log goes to `%TEMP%\english_tutor\logs` and a warning says so. Errors raised inside the window are logged there too. **Delete conversation logs** does not remove it.

### Not included, on purpose

| Not offered | Why |
| --- | --- |
| Accounts, login, cloud sync | There is no backend: the app is offline by design and sync would contradict that |
| Update channels | There are no published releases to update from |
| Proxy and ports | Every connection is to localhost (Ollama); the only download is the one-time Whisper model |
| Live language switching, moving existing data to a new folder, tray icon | Language and data folder need a restart; moving data and a tray icon were left out to keep the app dependency-free |

## Push-to-talk key

The default is **V** (`TUTOR_PTT_KEY=v`). The hook does not suppress key presses, so while you hold V with another application focused, that application also receives the letter. If that bothers you, use a non-printing key such as `TUTOR_PTT_KEY=right ctrl`. Names such as `f9` or `space` are standard `keyboard` names but were not exercised while writing this document.

Left and right Ctrl share one scan code, and the `keyboard` package matches modifier keys by scan code, so a plain registration for "right ctrl" would also fire on **left** Ctrl (every Ctrl+C). To avoid that, when the configured key is exactly `left ctrl`, `right ctrl`, `left alt` or `right alt`, the app asks Windows (`GetKeyNameTextW`) for the localized name of that side and accepts only events whose name is either the configured text or the localized one. For example, on Spanish Windows the right Ctrl key reports `CTRL DERECHA`, while the left one reports `CTRL`. If the lookup fails, no side filter is applied and push-to-talk still works (but the other side also triggers it). Any other key (for example `v` or `f9`) has no filter.

The key is not suppressed, so if you choose Right Ctrl, shortcuts that include it still reach the focused application and will also start a recording. Change the key in **Settings > Shortcuts**; the new key applies after a restart.

## Piper resolution order

`resolve_piper_exe` looks for the Piper executable in this order and stops at the first match:

1. `TUTOR_PIPER_EXE`, if set. **If it is set but the file does not exist, the result is "not found"; the later candidates are not tried.**
2. `<project root>\piper\piper.exe` (recommended)
3. `<project root>\english_teacher\piper\piper.exe` (location used by the old prototype; still works)
4. `<current directory>\piper\piper.exe`

The project root is the repository folder (two levels above `config.py`) when `pyproject.toml` exists there, otherwise the current directory.

The voice defaults to `voices\en_US-lessac-medium.onnx` inside the folder where `piper.exe` was found (or `<project root>\piper\voices\...` when it was not found). `TUTOR_PIPER_VOICE` overrides it.

Piper counts as available only if the executable, the `.onnx` voice and the `.onnx.json` file all exist. Otherwise the app uses the text-only synthesizer, logs a warning (`Text-only (Piper not found or voice files missing: ...)`) and shows `Voice output unavailable: replies are text-only.` in the chat. Setting `TUTOR_TTS=0` skips Piper entirely.

## Local data

The app writes these files under the data folder (`TUTOR_DATA_DIR` or the **Data folder** setting, default `<project root>\data`, which is `data\` in the repository when running from source): the conversation logs and the mistake history described below, plus `settings.json` ([Settings file](#settings-file)) and `logs\app.log` ([Application log](#application-log)). `data/`, `logs/` and `*.log` are git-ignored.

### Conversation logs

`data\conversations\session-YYYYmmdd-HHMMSS.log`, one file per session. The file is created on the first logged entry, not at start-up. A new file starts after **End session** (the report is the last entry of the old file). If the app is closed without ending the session, the file simply stops there. If the name already exists, `-2`, `-3`, ... is appended.

The first line is `# English tutor conversation - <timestamp>`. Every entry is `[YYYY-MM-DD HH:MM:SS] LABEL: text`:

| Label | Written when |
| --- | --- |
| `YOU` | After each transcription, **before** the tutor is called. The raw Whisper text is written verbatim |
| `ALEX` | The tutor reply (or, in practice mode, the next question) |
| `TIP` | The live correction, as `"original" -> "corrected" (explanation) [major]` |
| `NATURAL` | A more natural way to say a correct sentence (only when [Suggest more natural phrasing](#general) is on) |
| `PAUSE` | A long pause inside the sentence just said, as `think how's … everything (You paused 1.7 s between 'how's' and 'everything'.)` |
| `REPORT` | The end-of-session report text |
| `PRACTICE` | `Started: 'orig' -> 'corr'`, each verdict as `[correct] feedback` (or `[incorrect]`, `[not_used]`), and `Stopped practice` |

Multi-line entries (the report) continue on following lines indented by four spaces. Each entry opens, appends and closes the file (UTF-8, LF), so a crash loses nothing already written. Example:

```text
# English tutor conversation - 2026-11-12 14:03:22
[2026-11-12 14:03:30] YOU: Yesterday I go to the park with my sister.
[2026-11-12 14:03:33] ALEX: That sounds lovely! What did you two do at the park?
[2026-11-12 14:03:33] TIP: "I go" -> "I went" (Use the past tense for yesterday.) [major]
```

### Mistake history

`data\mistakes.json`, versioned JSON:

```json
{
  "version": 1,
  "mistakes": [
    {
      "original": "I go", "corrected": "I went",
      "explanation": "Use the past tense for yesterday.", "severity": "major",
      "count": 3,
      "first_seen": "2026-11-12T14:03:30", "last_seen": "2026-11-12T15:10:02",
      "examples": ["Yesterday I go to the park with my sister."],
      "practice": {"attempts": 2, "successes": 1}
    }
  ]
}
```

- **Grouping.** Corrections are grouped by the normalised `original => corrected` pair (lower-case, punctuation removed except apostrophes). Repeating a pair increments `count`, updates `last_seen`, keeps `first_seen`, keeps the latest non-empty explanation, and stores up to the last 3 distinct example sentences. Severity becomes `major` if any occurrence was major. Long pauses are stored the same way with `"severity": "hesitation"` (shown as `PAUSE`); their `original` holds the words with `…` where the pause was and `corrected` the same words without it. An older version of the app skips such entries when it reads the file, and drops them the next time it saves.
- **Optional fields.** An entry may also carry `"category"` (the kind of mistake, a short text) and `"review": {"due": "2026-11-14", "step": 2}` (when it is next due for review and its position in the review ladder). They are written only when set and are read leniently: a damaged `review` is dropped and the mistake is kept. They live inside version 1; an older build ignores them and drops them the next time it saves.
- **Category.** `"category"` holds the kind of mistake (`verb_tense`, `prepositions`, ... or `fluency` for pauses); see [tutor-behavior.md](tutor-behavior.md#correction-policy).
- **What is counted.** Every correction that survives the code guards, in normal conversation turns only (major and minor, not only the live one). Practice turns add only to `practice.attempts` / `practice.successes` (a `correct` result adds an attempt and a success, `incorrect` adds an attempt, `not_used` adds nothing) and do not change `last_seen`.
- **Saving.** After every change the file is written to `mistakes.json.tmp` in the same folder, flushed, and swapped in with `os.replace`, so a failed save never destroys the previous file.
- **Corrupt or unsupported file.** If the file is not valid JSON, has the wrong structure or a `version` other than 1, it is renamed to `mistakes.json.corrupt-YYYYmmdd-HHMMSS`, the app shows `Mistake history was unreadable; saved a copy as <name> and started a new one`, and starts with an empty history. If the rename itself fails, the store becomes read-only for that run (nothing is overwritten) and a message says so. Single bad entries inside a valid file are skipped with a console warning.
- **Failures never block a turn.** Storage problems (log or history) are shown once per kind as a chat notice (`Conversation log unavailable: ...`, `Mistake history not saved: ...`) and logged as console warnings; the conversation continues and the in-memory history stays correct for the run.

### Session statistics

`data\sessions.json`, versioned JSON, one entry per finished session (written when you press **End session**, only if you answered at least once):

```json
{
  "version": 1,
  "sessions": [
    {
      "started_at": "2026-11-13T10:00:00", "duration_s": 300.0,
      "turns": 5, "words": 80, "speech_s": 40.0,
      "major": 2, "minor": 3, "pauses": 1, "slow_starts": 1,
      "categories": {"prepositions": 2, "verb_tense": 1}
    }
  ]
}
```

- **Numbers.** `duration_s` runs from the first answer to the end of the session; `speech_s` is the recorded speech (used for words per minute); `major` / `minor` count every correction made, repeats included; `pauses` and `slow_starts` count long pauses inside sentences and before the first word; `categories` (optional) counts the corrections per kind of mistake, leaving out `other`. Quitting without pressing **End session** stores nothing for that run.
- **Saving, corrupt file, failures.** Same rules as the mistake history: atomic swap of `sessions.json.tmp`, a bad file is renamed to `sessions.json.corrupt-YYYYmmdd-HHMMSS` and a new one starts, bad entries are skipped, and a failed save shows `Session statistics not saved: ...` once and never blocks the report.

### Wiping the data

The easy way is **Settings > Storage > Delete conversation logs / Delete mistake history** (with confirmation, [details](#storage)). To do it by hand, close the app, then delete what you want to forget:

```powershell
Remove-Item -Recurse -Force data                      # everything, including settings.json
Remove-Item -Recurse -Force data\conversations        # logs only
Remove-Item data\mistakes.json                        # mistake history only
Remove-Item data\sessions.json                        # session statistics only
```

Use the path of your `TUTOR_DATA_DIR` if you changed it. Files are plain, unencrypted text; see [security-notes.md](security-notes.md).

## Setting variables in PowerShell

For the current terminal only:

```powershell
$env:TUTOR_PTT_KEY = "f9"
$env:TUTOR_OLLAMA_MODEL = "llama3:8b-instruct-q4_K_M"
$env:TUTOR_PIPER_EXE = "C:\tools\piper\piper.exe"
english-tutor
```

Persistently for your user account (applies to terminals opened afterwards):

```powershell
[Environment]::SetEnvironmentVariable("TUTOR_PTT_KEY", "f9", "User")
```

Remove a variable:

```powershell
Remove-Item Env:TUTOR_PTT_KEY                                        # current terminal
[Environment]::SetEnvironmentVariable("TUTOR_PTT_KEY", $null, "User")  # persistent
```

Show what is currently set:

```powershell
Get-ChildItem Env:TUTOR_*
```

## Fixed values (not configurable)

These are constants in the code and have no environment variable: Ollama `num_ctx` 4096, `keep_alive` 10 minutes, connect timeout 5 s, `/api/tags` check timeout 3 s, Piper synthesis timeout 60 s, recorder block size 1024 and post-roll 0.3 s, minimum clip length 0.25 s, silence peak threshold 0.01, report window of the last 40 turns, UI refresh interval 30 ms. The Whisper decoding options are listed in [tutor-behavior.md](tutor-behavior.md#literal-transcription).
