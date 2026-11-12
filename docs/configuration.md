# Configuration

All settings are read once at start-up from environment variables (`config.load_config`). Every variable is optional. An empty or whitespace-only value counts as "not set" and the default is used.

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
| `TUTOR_PTT_KEY` | string | `right ctrl` | Push-to-talk key, as a key name understood by the `keyboard` package. Shown capitalised (`Right Ctrl`, `V`) in the window hint and in the `Ready: hold <KEY>` status. See [Push-to-talk key](#push-to-talk-key) |
| `TUTOR_DATA_DIR` | path | `<project root>\data` | Folder for the conversation logs and the mistake history. A relative path is relative to the working directory. See [Local data](#local-data) |
| `TUTOR_LOG_LEVEL` | string | `INFO` | Python logging level name (`DEBUG`, `INFO`, `WARNING`, ...). Upper-cased; an unknown name falls back to `INFO`. Logs go to the console |

Notes:

- Numbers are parsed with Python's `int()` / `float()`. Ranges are enforced for the four numeric variables above; `nan` and `inf` are rejected for the float ones. Error texts: `must be greater than 0`, `must be 0 or greater`, `must be 1 or greater`.
- Use **absolute paths** for `TUTOR_PIPER_EXE` and `TUTOR_PIPER_VOICE`. Availability is checked against the app's working directory, whereas Piper itself is started with the folder of `piper.exe` as its working directory and receives the voice path unchanged.

## Push-to-talk key

The default is **Right Ctrl** (`TUTOR_PTT_KEY=right ctrl`). It was chosen because it is a non-printing key, so holding it does not type anything into the window that has focus. Set `TUTOR_PTT_KEY=v` to get the previous default (a letter key *is* typed into other applications, because the hook does not suppress key presses). Names such as `f9` or `space` are standard `keyboard` names but were not exercised while writing this document.

Left and right Ctrl share one scan code, and the `keyboard` package matches modifier keys by scan code, so a plain registration for "right ctrl" would also fire on **left** Ctrl (every Ctrl+C). To avoid that, when the configured key is exactly `left ctrl`, `right ctrl`, `left alt` or `right alt`, the app asks Windows (`GetKeyNameTextW`) for the localized name of that side and accepts only events whose name is either the configured text or the localized one. For example, on Spanish Windows the right Ctrl key reports `CTRL DERECHA`, while the left one reports `CTRL`. If the lookup fails, no side filter is applied and push-to-talk still works (but the other side also triggers it). Any other key (for example `v` or `f9`) has no filter.

The key is not suppressed, so shortcuts that include Right Ctrl still reach the focused application and will also start a recording.

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

The app writes two kinds of files under the data folder (`TUTOR_DATA_DIR`, default `<project root>\data`, which is `data\` in the repository when running from source). `data/`, `logs/` and `*.log` are git-ignored.

### Conversation logs

`data\conversations\session-YYYYmmdd-HHMMSS.log`, one file per session. The file is created on the first logged entry, not at start-up. A new file starts after **End session** (the report is the last entry of the old file). If the app is closed without ending the session, the file simply stops there. If the name already exists, `-2`, `-3`, ... is appended.

The first line is `# English tutor conversation - <timestamp>`. Every entry is `[YYYY-MM-DD HH:MM:SS] LABEL: text`:

| Label | Written when |
| --- | --- |
| `YOU` | After each transcription, **before** the tutor is called. The raw Whisper text is written verbatim |
| `ALEX` | The tutor reply (or, in practice mode, the next question) |
| `TIP` | The live correction, as `"original" -> "corrected" (explanation) [major]` |
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

- **Grouping.** Corrections are grouped by the normalised `original => corrected` pair (lower-case, punctuation removed except apostrophes). Repeating a pair increments `count`, updates `last_seen`, keeps `first_seen`, keeps the latest non-empty explanation, and stores up to the last 3 distinct example sentences. Severity becomes `major` if any occurrence was major.
- **What is counted.** Every correction that survives the code guards, in normal conversation turns only (major and minor, not only the live one). Practice turns add only to `practice.attempts` / `practice.successes` (a `correct` result adds an attempt and a success, `incorrect` adds an attempt, `not_used` adds nothing) and do not change `last_seen`.
- **Saving.** After every change the file is written to `mistakes.json.tmp` in the same folder, flushed, and swapped in with `os.replace`, so a failed save never destroys the previous file.
- **Corrupt or unsupported file.** If the file is not valid JSON, has the wrong structure or a `version` other than 1, it is renamed to `mistakes.json.corrupt-YYYYmmdd-HHMMSS`, the app shows `Mistake history was unreadable; saved a copy as <name> and started a new one`, and starts with an empty history. If the rename itself fails, the store becomes read-only for that run (nothing is overwritten) and a message says so. Single bad entries inside a valid file are skipped with a console warning.
- **Failures never block a turn.** Storage problems (log or history) are shown once per kind as a chat notice (`Conversation log unavailable: ...`, `Mistake history not saved: ...`) and logged as console warnings; the conversation continues and the in-memory history stays correct for the run.

### Wiping the data

Close the app, then delete what you want to forget:

```powershell
Remove-Item -Recurse -Force data                      # everything
Remove-Item -Recurse -Force data\conversations        # logs only
Remove-Item data\mistakes.json                        # mistake history only
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
