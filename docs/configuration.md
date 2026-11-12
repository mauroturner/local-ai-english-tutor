# Configuration

All settings are read once at start-up from environment variables (`config.load_config`). Every variable is optional. An empty or whitespace-only value counts as "not set" and the default is used.

If a value is invalid the app prints `Configuration error: <message>` to standard error and exits with code `2` before opening a window. The message names the variable, for example `TUTOR_HISTORY_EXCHANGES must be an integer, got 'abc'`.

## Variables

| Variable | Type | Default | Effect |
| --- | --- | --- | --- |
| `TUTOR_OLLAMA_URL` | string | `http://localhost:11434` | Base URL of the Ollama server. A trailing `/` is removed. See [security-notes.md](security-notes.md) |
| `TUTOR_OLLAMA_MODEL` | string | `llama3:8b-instruct-q4_K_M` | Model used for replies and feedback. It must already be pulled; see [tutor-behavior.md](tutor-behavior.md#using-a-bigger-model) |
| `TUTOR_OLLAMA_TIMEOUT` | float (seconds) | `120` | Read timeout for `/api/chat` calls. The connect timeout is fixed at 5 s. On expiry the app shows `Ollama timed out after <n>s` |
| `TUTOR_LLM_TEMPERATURE` | float | `0.5` | Sampling temperature sent to Ollama |
| `TUTOR_HISTORY_EXCHANGES` | integer >= 0 | `6` | How many learner/tutor exchanges are sent back to the model as memory. `0` disables memory. Negative values are rejected |
| `TUTOR_WHISPER_MODEL` | string | `large-v3` | faster-whisper model name or path. Downloaded on first use if it is a model name |
| `TUTOR_WHISPER_DEVICE` | string | `auto` | `auto` and `cuda` try the GPU first and fall back to CPU if loading or the warm-up decode fails. Any other value (use `cpu`) loads on the CPU directly. The value is lower-cased; it is not validated |
| `TUTOR_WHISPER_COMPUTE_TYPE` | string | `float16` | Compute type for the GPU attempt |
| `TUTOR_WHISPER_CPU_COMPUTE_TYPE` | string | `int8` | Compute type for the CPU (fallback or `cpu` device) |
| `TUTOR_WHISPER_BEAM_SIZE` | integer | `5` | Beam size passed to Whisper |
| `TUTOR_TTS` | boolean | `1` | Voice output. Accepted: `1`, `true`, `yes`, `on` / `0`, `false`, `no`, `off` (case-insensitive). When off, the app is text-only and logs `Voice output disabled (TUTOR_TTS=0).` |
| `TUTOR_PIPER_EXE` | path | auto-detected | Path to `piper.exe`. See [Piper resolution order](#piper-resolution-order) |
| `TUTOR_PIPER_VOICE` | path | `<folder of piper.exe>\voices\en_US-lessac-medium.onnx` | Voice model. A file with the same name plus `.json` (for example `en_US-lessac-medium.onnx.json`) must sit next to it |
| `TUTOR_PTT_KEY` | string | `v` | Push-to-talk key, as a key name understood by the `keyboard` package. Also used in the window hint and the `Ready: hold <KEY>` status |
| `TUTOR_LOG_LEVEL` | string | `INFO` | Python logging level name (`DEBUG`, `INFO`, `WARNING`, ...). Upper-cased; an unknown name falls back to `INFO`. Logs go to the console |

Notes:

- Numbers are parsed with Python's `int()` / `float()`. Only `TUTOR_HISTORY_EXCHANGES` has a range check; the other numeric values are not range-checked.
- `TUTOR_PTT_KEY`: the code passes the key to `keyboard.on_press_key` / `on_release_key` without suppression, so the key press is still delivered to whatever window has focus. A letter key such as `v` will therefore also type that letter in other applications while the app runs. Names such as `f9` or `space` are standard `keyboard` names, but they were not exercised while writing this document.
- Use **absolute paths** for `TUTOR_PIPER_EXE` and `TUTOR_PIPER_VOICE`. Availability is checked against the app's working directory, whereas Piper itself is started with the folder of `piper.exe` as its working directory and receives the voice path unchanged.

## Piper resolution order

`resolve_piper_exe` looks for the Piper executable in this order and stops at the first match:

1. `TUTOR_PIPER_EXE`, if set. **If it is set but the file does not exist, the result is "not found"; the later candidates are not tried.**
2. `<project root>\piper\piper.exe` (recommended)
3. `<project root>\english_teacher\piper\piper.exe` (location used by the old prototype; still works)
4. `<current directory>\piper\piper.exe`

The project root is the repository folder (two levels above `config.py`) when `pyproject.toml` exists there, otherwise the current directory.

The voice defaults to `voices\en_US-lessac-medium.onnx` inside the folder where `piper.exe` was found (or `<project root>\piper\voices\...` when it was not found). `TUTOR_PIPER_VOICE` overrides it.

Piper counts as available only if the executable, the `.onnx` voice and the `.onnx.json` file all exist. Otherwise the app uses the text-only synthesizer, logs a warning (`Text-only (Piper not found or voice files missing: ...)`) and shows `Voice output unavailable: replies are text-only.` in the chat. Setting `TUTOR_TTS=0` skips Piper entirely.

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
