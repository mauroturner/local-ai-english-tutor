# Troubleshooting

Logs are written to the console where you started the app (level set by `TUTOR_LOG_LEVEL`; use `DEBUG` for more detail). Messages shown inside the app appear as orange notice lines in the chat. Settings are described in [configuration.md](configuration.md).

## The app exits immediately with `Configuration error: ...`

A `TUTOR_*` variable has an invalid value (for example a non-integer `TUTOR_HISTORY_EXCHANGES`). The message names the variable. Fix or remove it (`Remove-Item Env:TUTOR_HISTORY_EXCHANGES`). Exit code is `2`.

## CUDA / cuDNN / cuBLAS errors (Whisper)

Typical symptoms in the console: `CUDA unavailable (...); falling back to CPU`, or DLL-loading errors about the cuBLAS or cuDNN libraries.

- On start-up the app loads Whisper on the GPU (`float16`) and runs one warm-up decode, because missing CUDA libraries often fail only on the first decode. If anything fails, it **automatically reloads the model on the CPU with `int8`** and continues. You only see the warning in the console; the app works, just more slowly.
- To use the GPU, install an NVIDIA driver plus CUDA 12 cuBLAS and cuDNN 9, and make sure their DLL folders are on `PATH`.
- To skip the GPU attempt (and the warning), set `TUTOR_WHISPER_DEVICE=cpu`.
- CPU decoding with `large-v3` is slow. A smaller model such as `TUTOR_WHISPER_MODEL=small` is faster but less accurate (not tested here).
- If even the CPU load fails, the chat shows `Speech model failed to load: ...` and the status stays on `Loading speech model...`. Recording is not possible until you fix the cause (for example no network on the first run, so the model cannot be downloaded) and restart the app.

## First start is very slow

On first run faster-whisper downloads `large-v3` (about 3 GB) from Hugging Face. Later starts load it from the local cache. The first reply from Ollama can also take about 40 seconds while the model loads into memory.

## Ollama is not running or the model is not pulled

The app checks Ollama at start-up and shows a notice, but stays open. Messages:

| Message | Fix |
| --- | --- |
| ``Ollama not reachable at http://localhost:11434: run `ollama serve` `` | Start Ollama (`ollama serve` or the tray app). Check `TUTOR_OLLAMA_URL` |
| ``Model llama3:8b-instruct-q4_K_M not found: run `ollama pull llama3:8b-instruct-q4_K_M` `` | Run the `ollama pull` command shown (or set `TUTOR_OLLAMA_MODEL` to a model you have). Check installed models with `ollama list` |
| `Unexpected response from Ollama at ...` | The URL answers but is not an Ollama server, or the reply format is unexpected |
| `Ollama timed out after 120s` | The model is slow or still loading. Retry, or raise `TUTOR_OLLAMA_TIMEOUT` |
| `Ollama request failed: ...` | Other HTTP or response errors; see the console log |

After you fix the problem, you do not need to restart: the next turn calls Ollama again. If a turn fails, your transcript stays in the chat, no tutor reply is added, and the turn is not stored in the history.

## No voice (text-only mode)

The chat shows `Voice output unavailable: replies are text-only.` and the console shows `Text-only (Piper not found or voice files missing: ...)`. Piper is used only when **all three** exist:

- `piper.exe` (resolution order in [configuration.md](configuration.md#piper-resolution-order)),
- the voice `en_US-lessac-medium.onnx`,
- the voice config `en_US-lessac-medium.onnx.json` (a very common omission).

Check the layout `piper\piper.exe` and `piper\voices\en_US-lessac-medium.onnx` + `.onnx.json`. If you set `TUTOR_PIPER_EXE` to a path that does not exist, the other locations are **not** tried. If the message was `Voice output disabled (TUTOR_TTS=0).`, remove `TUTOR_TTS` or set it to `1`.

If playback fails on a single turn, the failure is logged (`Speech synthesis failed, continuing text-only`) and the reply stays visible in the chat.

## Push-to-talk does not respond

- The key is a **global keyboard hook** (the `keyboard` package). On some systems installing the hook needs elevated rights: run the terminal as administrator. If the hook cannot be installed the chat shows `PTT unavailable: <error>`.
- Wait for the status `Ready: hold V`. Presses are ignored while the app is loading, transcribing, thinking, speaking or writing the report.
- Hold the key until you finish speaking, then release. Auto-repeat is ignored.
- Change the key with `TUTOR_PTT_KEY` (for example `$env:TUTOR_PTT_KEY = "f9"`). The window hint and status line show the configured key.
- The key press is not suppressed, so a letter key types that letter in the focused application.

## Wrong or duplicated microphone

Windows exposes each microphone through several audio APIs (MME, DirectSound, WASAPI), which would show up as duplicates. The app keeps one entry per device, preferring **WASAPI over DirectSound over MME**, and merges entries by the first 31 characters of the name (MME truncates names). Output-only devices are excluded and at most 2 channels are used.

- Pick the right device in the **Select Microphone** drop-down; the choice applies to the next recording.
- If the drop-down shows `None`, no input device was found; recording fails with `Could not start recording: No input device available`.
- Watch the **Audio Level** bar while speaking: if it does not move, the wrong device is selected or Windows privacy settings block microphone access for desktop apps.

## `Too short or too quiet, try again`

The recording was shorter than 0.25 seconds or its peak level was below 0.01. Hold the key a little longer, speak closer to the microphone or choose another device. `Didn't catch that, try again` means audio was accepted but Whisper returned no text (for example only noise or silence).

## Other messages

| Message | Meaning |
| --- | --- |
| `Transcription failed: ...` | Whisper raised an error while decoding; the state returns to idle |
| `Recording failed: ...` / `Could not start recording: ...` | The audio device could not be stopped or started |
| `Voice output failed: ...` | An unexpected error in audio playback; the text reply is still shown |
| `Unexpected error: ...` | Last-resort guard; the session returns to idle. Check the console log |
| `Feedback unavailable: ...` | The report was built but the feedback request failed |

## Running the tests fails

Run `pip install -e ".[dev]"` inside the activated virtual environment, then `pytest`. The tests need no GPU, microphone or network.
