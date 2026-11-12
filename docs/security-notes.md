# Security notes

## Everything runs locally

Speech recognition (faster-whisper), the language model (Ollama) and speech synthesis (Piper) all run on your machine. Microphone audio is kept in memory and passed to Whisper as an array; the app does not write it to disk. The code does not log transcript text. The only network traffic the app itself triggers is:

- the one-time Whisper model download from Hugging Face on first run (performed by faster-whisper), and
- HTTP requests to the Ollama server at `TUTOR_OLLAMA_URL`.

## Keep `TUTOR_OLLAMA_URL` on localhost

Your transcripts, the conversation history and the end-of-session text are sent to `TUTOR_OLLAMA_URL` as plain-text JSON over HTTP, with no authentication or encryption added by the app. The default is `http://localhost:11434`. Only point it at another host if you fully trust that host and the network path between you and it.

## `TUTOR_PIPER_EXE` is executed as-is

The file named by `TUTOR_PIPER_EXE` (or found by the [resolution order](configuration.md#piper-resolution-order), including `piper\piper.exe` in the repository and in the current directory) is started as a subprocess with an argument list (no shell) each time the tutor speaks. Only use a Piper binary you downloaded from a source you trust, and do not run the app from a directory whose `piper\piper.exe` you did not place there. Likewise, treat environment variables as trusted input: anyone who can set them for your session can choose which executable runs.

The text to be spoken is passed to Piper on standard input, with newlines replaced by spaces.

## Temporary audio

Synthesised speech is written to a temporary WAV file created with `tempfile.mkstemp` in the system temp folder. It is played and then deleted in a `finally` block, so it is removed even when playback or synthesis fails.

## Global keyboard hook

Push-to-talk uses the `keyboard` package, which installs a system-wide hook. The app only reacts to the configured key (`TUTOR_PTT_KEY`) and does not store or log other key presses, but the hook is active while the app runs, including when other windows have focus. Some security software flags such hooks.

## Git hygiene

`.gitignore` excludes the Piper binaries and voices (`piper/`, `*.exe`, `*.dll`, `*.onnx`, `*.onnx.json`), virtual environments, `*.wav` files and `.env`, so downloaded binaries and local secrets are not committed by accident.
