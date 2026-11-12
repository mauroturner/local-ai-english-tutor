# Local AI English Tutor

Practise spoken English with a conversation partner that runs **fully offline** on your Windows PC.

You hold a key and talk. The app transcribes your speech with Whisper, sends it to a local language model (Ollama), and the tutor answers out loud with a Piper voice.

- **Literal transcription.** The text shown in the chat is exactly what Whisper heard. It is never rewritten by the language model or by app code.
- **Conversation first.** The tutor replies to what you said and ends with a follow-up question. It remembers the last few exchanges.
- **Live correction only for clear mistakes.** At most one clearly marked error per turn is shown (and spoken) right away. Smaller slips are recorded silently.
- **End-of-session report.** Click **End session** to get the list of errors (original -> corrected, with the reason) and overall feedback.

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
english-tutor
# or
python -m english_tutor
```

The first start loads Whisper (the status line shows `Loading speech model...`) and then `Ready: hold V`. If Ollama or the model is missing, the chat shows a notice but the app stays open; see [docs/troubleshooting.md](docs/troubleshooting.md).

## Usage

1. Choose your microphone in the **Select Microphone** drop-down (the system default is preselected; duplicate entries from different Windows audio APIs are merged).
2. **Hold the push-to-talk key** (default `V`), speak, and release to send. The key is global: it works even when the app window is not focused.
3. Your transcript appears as `You: ...`, then the tutor's reply as `Alex: ...`. When a clearly marked mistake was found, a highlighted `Tip: "..." -> "..."` card follows, and the tip is spoken before the reply.
4. Click **End session** (enabled only when the app is idle) to get the session report. Starting a new conversation afterwards begins with an empty history.

Details of what is shown, spoken and recorded: [docs/tutor-behavior.md](docs/tutor-behavior.md).

## Configuration

All settings are optional environment variables prefixed with `TUTOR_` (Ollama URL and model, Whisper model and device, Piper paths, push-to-talk key, history length, log level, and more). Example:

```powershell
$env:TUTOR_PTT_KEY = "f9"
english-tutor
```

Full table with defaults and validation: [docs/configuration.md](docs/configuration.md).

## Tests

```powershell
pytest
```

The tests use fakes: no microphone, GPU, Ollama or network is needed.

## Project layout

```text
src/english_tutor/
  __main__.py          composition root (entry point)
  config.py            TUTOR_* environment variables -> AppConfig
  ports.py             interfaces (Protocols) and adapter errors
  domain/              models, correction rules, prompts and JSON schemas
  application/         ConversationSession, events, history, SerialWorker
  audio/               audio processing and microphone discovery
  adapters/            Whisper, Ollama, Piper, sounddevice, keyboard
  ui/                  customtkinter window and widgets
tests/                 pytest suite
docs/                  technical documentation
```

## Documentation

- [Architecture](docs/architecture.md): layers, ports and adapters, threading, failure recovery
- [Data flow](docs/data-flow.md): one conversation turn and the end-of-session report
- [Configuration](docs/configuration.md): every `TUTOR_*` variable, Piper resolution
- [Tutor behavior](docs/tutor-behavior.md): transcription, correction policy, prompts, model limits
- [Troubleshooting](docs/troubleshooting.md)
- [Security notes](docs/security-notes.md)

## Upgrading from the old prototype

The earlier prototype needed a custom Ollama model called `english-teacher`. It is **no longer needed**: the tutor prompts now live in the code ([`domain/prompts.py`](src/english_tutor/domain/prompts.py)) and the app talks to the plain `llama3:8b-instruct-q4_K_M` model.
