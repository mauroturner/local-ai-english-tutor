# Local AI English Tutor

Practise spoken English with a conversation partner that runs **fully offline** on your Windows PC.

You hold a key and talk. The app transcribes your speech with Whisper, sends it to a local language model (Ollama), and the tutor answers out loud with a Piper voice.

- **Literal transcription.** The text shown in the chat is exactly what Whisper heard. It is never rewritten by the language model or by app code.
- **Conversation first.** The tutor replies to what you said and ends with a follow-up question. It remembers the last few exchanges.
- **Live correction only for clear mistakes.** At most one clearly marked error per turn is shown (and spoken) right away. Smaller slips are recorded silently.
- **End-of-session report.** Click **End session** to get the list of errors (original -> corrected, with the reason) and overall feedback.
- **Local history and targeted practice.** Every conversation is saved as a `.log` file on your disk, recurring mistakes are collected in a **Mistakes** tab, and a **Practice** button runs a short spoken drill on one specific mistake.

No cloud service is used at run time. The only download is the one-time Whisper model fetch (see [Requirements](#requirements)).

## Requirements

| Component | Details |
| --- | --- |
| OS | Windows 10 or 11 |
| Python | 3.11 |
| Ollama | Installed and running, with the model pulled: `ollama pull llama3:8b-instruct-q4_K_M` |
| GPU (optional) | NVIDIA GPU with CUDA 12 cuBLAS and cuDNN 9 for faster-whisper. Without it the app falls back to CPU (`int8`), which is slower |
| Disk / network | About 3 GB one-time download of Whisper `large-v3` from Hugging Face on first run |
| Piper (optional) | Without Piper the app works in text-only mode (no spoken replies) |

### Piper (text to speech)

1. Download the Windows release `piper_windows_amd64.zip` (tag `2023.11.14-2`) from <https://github.com/rhasspy/piper/releases> and extract it into a `piper/` folder at the repository root, so that `piper\piper.exe` exists.
2. Download **both** voice files from <https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium> into `piper\voices\`:
   - `en_US-lessac-medium.onnx`
   - `en_US-lessac-medium.onnx.json` (required; without it Piper is treated as unavailable)

Expected layout:

```text
piper/
  piper.exe          (plus the other files from the zip)
  voices/
    en_US-lessac-medium.onnx
    en_US-lessac-medium.onnx.json
```

The `piper/` folder, `*.onnx`, `*.onnx.json`, `*.exe` and `*.dll` are git-ignored, so none of this is committed. To use a different location, see [docs/configuration.md](docs/configuration.md#piper-resolution-order).

## Setup

In PowerShell:

```powershell
git clone https://github.com/mauroturner/local-ai-english-tutor.git
cd local-ai-english-tutor

py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install -e ".[dev]"
```

If PowerShell refuses to run `Activate.ps1`, allow local scripts once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

`requirements.txt` holds the exact versions the project was tested with. `pip install -e ".[dev]"` installs the `english_tutor` package (and the `english-tutor` command) in editable mode, plus `pytest`.

## Run

Make sure Ollama is running (`ollama serve`, or the Ollama tray app), then:

```powershell
python main.py
```

`main.py` at the repository root is the entry point. It works even without `pip install -e`, because it adds `src/` to the import path. After `pip install -e ".[dev]"` the `english-tutor` command and `python -m english_tutor` start the same app.

The first start loads Whisper (the status line shows `Loading speech model...`) and then `Ready: hold V`. If Ollama or the model is missing, the chat shows a notice but the app stays open; see [docs/troubleshooting.md](docs/troubleshooting.md).

## Usage

1. Choose your microphone in the **Select Microphone** drop-down (the system default is preselected; duplicate entries from different Windows audio APIs are merged).
2. **Hold the push-to-talk key** (default **V**), speak, and release to send. The key is global: it works even when the app window is not focused, and because it is not suppressed, a focused text field in another application also receives the letter. To use another key, set `TUTOR_PTT_KEY` (for example `right ctrl`, a non-printing key; the left Ctrl is then ignored); see [docs/configuration.md](docs/configuration.md).
3. Your transcript appears as `You: ...`, then the tutor's reply as `Alex: ...`. When a clearly marked mistake was found, a highlighted `Tip: "..." -> "..."` card follows, and the tip is spoken before the reply.
4. Click **End session** (enabled only when the app is idle and no practice is running) to get the session report. Starting a new conversation afterwards begins with an empty chat history.

Details of what is shown, spoken and recorded: [docs/tutor-behavior.md](docs/tutor-behavior.md).

### Mistakes tab and practice mode

Every correction the tutor finds (major and minor) is added to a persistent list, grouped by the normalised `original -> corrected` pair, with a counter. It survives restarts and is not cleared by **End session**.

1. Open the **Mistakes** tab. Rows are sorted by frequency (then most recent) and show severity, the pair, how many times it occurred, the last date and your practice score (`practice successes/attempts`). Up to 50 rows are shown.
2. Click **Practice** on a row (enabled only when the app is idle). The app switches to the **Chat** tab, a banner `Practicing: "..." -> "..."` appears, and Alex introduces the drill and asks a question.
3. Answer by holding the push-to-talk key. For each answer the coach judges **only the target structure**: `correct`, `incorrect` (you get the corrected sentence) or `not_used` (a reminder), then asks the next question.
4. Click **Stop practice** to return to the normal conversation.

Practice turns do not run the general correction pipeline: other mistakes in your answer are ignored, nothing is added to the session report, and the normal chat memory is untouched. Only `correct` and `incorrect` results change the practice score.

### Local data

The app stores two things under `data/` (or the folder in `TUTOR_DATA_DIR`), both ignored by git:

| Path | Content |
| --- | --- |
| `data/conversations/session-YYYYmmdd-HHMMSS.log` | One text file per session. Lines look like `[2026-11-12 14:03:22] YOU: <raw transcript>`; the transcript is written verbatim |
| `data/mistakes.json` | The mistake history (versioned JSON) |

To wipe your history, close the app and delete the `data` folder (or just `data\conversations` or `data\mistakes.json`). Details, including the file formats, are in [docs/configuration.md](docs/configuration.md#local-data) and [docs/security-notes.md](docs/security-notes.md).

## Configuration

All settings are optional environment variables prefixed with `TUTOR_` (Ollama URL and model, Whisper model and device, Piper paths, push-to-talk key, history length, data folder, log level, and more). Numeric values are range-checked at start-up. Example:

```powershell
$env:TUTOR_PTT_KEY = "right ctrl"   # use Right Ctrl instead of V
python main.py
```

Full table with defaults and validation: [docs/configuration.md](docs/configuration.md).

## Tests

```powershell
pytest
```

The tests use fakes: no microphone, GPU, Ollama or network is needed.

## Project layout

```text
main.py                entry point: python main.py
src/english_tutor/
  __main__.py          composition root (builds and starts the app)
  config.py            TUTOR_* environment variables -> AppConfig
  ports.py             interfaces (Protocols) and adapter errors
  domain/              models, correction rules, prompts and JSON schemas
  application/         ConversationSession, practice drill, mistake book, events, SerialWorker
  audio/               audio processing and microphone discovery
  adapters/            Whisper, Ollama, Piper, sounddevice, keyboard, log file, JSON store
  ui/                  customtkinter window, chat, Mistakes tab and widgets
tests/                 pytest suite
docs/                  technical documentation
data/                  created at run time: conversation logs and mistake history (git-ignored)
```

## Documentation

- [Architecture](docs/architecture.md): layers, ports and adapters, threading, failure recovery
- [Data flow](docs/data-flow.md): one conversation turn, a practice turn and the end-of-session report
- [Configuration](docs/configuration.md): every `TUTOR_*` variable, Piper resolution
- [Tutor behavior](docs/tutor-behavior.md): transcription, correction policy, practice mode, prompts, model limits
- [Troubleshooting](docs/troubleshooting.md)
- [Security notes](docs/security-notes.md): includes how the local data is stored

## Upgrading from the old prototype

The earlier single-file prototype (`english_teacher/assistant.py`) has been removed; start the app with `python main.py`. The prototype also needed a custom Ollama model called `english-teacher`. It is **no longer needed**: the tutor prompts now live in the code ([`domain/prompts.py`](src/english_tutor/domain/prompts.py)) and the app talks to the plain `llama3:8b-instruct-q4_K_M` model.
