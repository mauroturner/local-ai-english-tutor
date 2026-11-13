# Troubleshooting

Logs are written to `data\logs\app.log` and to the console where you started the app (level set in Settings > Advanced > Log detail or by `TUTOR_LOG_LEVEL`; use `DEBUG` for more detail; see [Getting logs for support](#getting-logs-for-support)). Messages shown inside the app appear as orange notice lines in the chat. Settings are described in [configuration.md](configuration.md).

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

The app checks Ollama at start-up and shows a notice, but stays open. You can also check it any time with **Settings > Advanced > Test connection** ([results](#test-connection-says)). Messages:

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
- The default key is **V**. Wait until the chip says **Ready** and the line under it says `Hold 'V' to speak, release to send` (during a drill it says `Practice: hold V to answer`). Presses are ignored while the app is loading, transcribing, thinking, speaking or writing the report, and **while the Settings window is open**.
- Hold the key until you finish speaking, then release. Auto-repeat is ignored.
- Change the key in **Settings > Shortcuts** (restart needed) or with `TUTOR_PTT_KEY`, for example `$env:TUTOR_PTT_KEY = "right ctrl"` (non-printing) or `"f9"`; the variable wins over the setting. The hold hint shows the configured key.
- **With `right ctrl`, left Ctrl is ignored on purpose.** The app tells the two Ctrl keys apart by the localized key name Windows reports (for example `CTRL DERECHA` for the right key on Spanish Windows). If that lookup fails, there is no side filter and either Ctrl key triggers recording. Side filtering applies only to `left`/`right` `ctrl`/`alt`.
- The key press is not suppressed. A letter key such as `v` is typed into the focused application, and shortcuts that use Right Ctrl also start a recording.

## Settings problems

| Symptom | Cause and fix |
| --- | --- |
| `Ignored invalid setting: <name> must be ..., got ...; using <default>.` | One value in `settings.json` was invalid (hand-edited, or from another version). Only that value falls back to its default. Open Settings and Save to rewrite the file |
| `Settings were unreadable; saved a copy as settings.json.corrupt-<timestamp> and started with defaults` | The file was not valid JSON or had an unsupported `version`. The copy is next to the original; nothing deletes it. Re-enter your choices in Settings |
| A setting is greyed out and says `Set by TUTOR_...` | An environment variable pins it. Remove the variable ([configuration.md](configuration.md#setting-variables-in-powershell)) and restart the terminal to edit it in the window |
| `Restart the app to apply: ...` banner | Those settings load at start-up. Click **Restart now** (it asks first if a conversation is in progress) or **Later** |
| **Save** is disabled | Nothing changed, or a field shows a red error (bad URL, shortcut conflict, ...). Fix the error under the row |
| `This folder cannot be used: ...` under the data or export folder | The folder cannot be created or written. Pick another one; the old data stays where it was (the app does not move it) |
| A shortcut is rejected | Shortcuts need Ctrl or Alt (bare F-keys are fine), cannot repeat, and cannot use reserved keys such as Ctrl+C or Alt+F4 ([list](configuration.md#shortcuts)) |
| Delete buttons say `Alex is busy right now` | Deleting is refused while the tutor is working or a practice drill is running. Wait until the status chip says Ready and stop the drill |
| Export report is disabled | There is no report yet. Click **End session** first |
| No sound cues | Check the three **Sound ...** switches in Audio & notifications and your default Windows output device. A cue is skipped if another one is still playing |
| No desktop notification | The toast appears only when the window is not focused. **Windows Focus Assist / Do not disturb** can hide it; the taskbar button flashes instead when it fails |
| Interface scale or theme looks wrong | Choose **Restore default settings** in Advanced, then **Save** |

### Test connection says...

Open **Settings > Advanced** and click **Test**. It checks the address and model currently typed in the form, even before saving.

| Result | Fix |
| --- | --- |
| Connected: Ollama is running and the model ... is installed | Nothing to do |
| Ollama is running, but the model ... is not installed | Run the `ollama pull <model>` command shown, or change the model name |
| Cannot reach Ollama at ... | Start Ollama (`ollama serve` or the tray app) and check the URL and port |
| Ollama at ... did not answer in time | The server is busy or blocked (firewall). Try again |
| That address is not valid | Use `http://` or `https://`, a host name and no query, for example `http://localhost:11434` |

### Start with Windows does not work

- The app does not start at sign-in: open Settings > General. If the row says the entry points to a different location, click **Save** to rewrite it. Check Task Manager > Startup apps that the entry is enabled.
- It starts but cannot find Piper or the data folder: Windows starts it from another working directory, so use absolute paths in `TUTOR_DATA_DIR`, `TUTOR_PIPER_EXE` and `TUTOR_PIPER_VOICE`.
- The first minutes after sign-in are slow, or the chat says Ollama is not reachable: Whisper is loading and Ollama may not be running yet. Wait, then use **Test connection**.
- To remove the entry by hand, see [configuration.md](configuration.md#start-with-windows).

## Getting logs for support

1. Open **Settings > Advanced > Open logs folder** (or go to `data\logs`).
2. Attach `app.log` (and `app.log.1` to `app.log.3` if they exist). For more detail set **Log detail** to `DEBUG`, reproduce the problem and attach the files again.
3. Check the files for personal paths first. They do not contain transcript text.

The log rotates at 1 MB and keeps 3 older files. If `data\logs` cannot be written, the log is in `%TEMP%\english_tutor\logs`.

## Wrong or duplicated microphone

Windows exposes each microphone through several audio APIs (MME, DirectSound, WASAPI), which would show up as duplicates. The app keeps one entry per device, preferring **WASAPI over DirectSound over MME**, and merges entries by the first 31 characters of the name (MME truncates names). Output-only devices are excluded and at most 2 channels are used.

- Pick the right device in the **Select Microphone** drop-down; the choice applies to the next recording.
- If the drop-down shows `None`, no input device was found; recording fails with `Could not start recording: No input device available`.
- Watch the **Audio Level** bar while speaking: if it does not move, the wrong device is selected or Windows privacy settings block microphone access for desktop apps.

## `Too short or too quiet, try again`

The recording was shorter than 0.25 seconds or its peak level was below 0.01. Hold the key a little longer, speak closer to the microphone or choose another device. `Didn't catch that, try again` means audio was accepted but Whisper returned no text (for example only noise or silence).

## Mistake history problems

- **`Mistake history was unreadable; saved a copy as mistakes.json.corrupt-<timestamp> and started a new one`.** `data\mistakes.json` was not valid JSON, had the wrong structure or an unsupported `version`. The app renamed it next to the original and started an empty history. Open the `.corrupt-...` file in a text editor to recover entries by hand if you need them; nothing deletes it.
- **`... could not be backed up; it is read-only this run`.** The rename failed (for example the file is open in another program). Nothing is overwritten and new mistakes are kept only in memory until you restart the app.
- **`Mistake history not saved: ...`.** The save failed (disk full, folder not writable, file locked). Mistakes stay in memory for this run and the conversation continues; the message appears once.
- Entries that cannot be parsed are skipped individually, with a console warning.

## Conversation log problems

- **`Conversation log unavailable: Could not write the conversation log: ...`.** The folder `data\conversations` (or `TUTOR_DATA_DIR\conversations`) could not be created or written, for example because the path is read-only, a file with that name exists, or the drive is missing. The notice appears once; the conversation continues without logging and each failure is also a console warning. Point `TUTOR_DATA_DIR` (or the **Data folder** setting) at a writable folder and restart.
- The log file is created when the first transcript is saved, not at start-up, so an empty folder right after launch is normal.

## Practice problems

- **`Practice is not available for that mistake.`** The selected entry no longer exists in memory or practice is not available; the session stays in normal conversation.
- Practice buttons are disabled unless the app is idle and no drill is running; **End session** is disabled during a drill. Click **Stop practice** first.
- If the same answer keeps scoring `not_used`, the coach's last question may not have called for the target form (a known limit of the 8B model; see [tutor-behavior.md](tutor-behavior.md#practice-mode)). Try answering with a sentence that uses the structure, or stop and restart the drill.

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
