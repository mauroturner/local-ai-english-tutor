# Data flow

This page follows the data through the application for the two main use cases. For the structure behind it see [architecture.md](architecture.md); for the rules applied to corrections see [tutor-behavior.md](tutor-behavior.md).

## One conversation turn

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant KB as KeyboardPushToTalk (hook thread)
    participant S as ConversationSession
    participant W as SerialWorker (worker thread)
    participant R as SoundDeviceRecorder
    participant STT as WhisperTranscriber
    participant LLM as OllamaTutorModel
    participant TTS as PiperSynthesizer
    participant UI as TutorWindow (Tk thread)

    User->>KB: hold PTT key (default V)
    KB->>S: on_ptt_press()
    S->>S: IDLE -> RECORDING
    S->>R: start(device_index)
    S-->>UI: StateChanged "Listening..."
    User->>KB: release key
    KB->>S: on_ptt_release()
    S->>S: RECORDING -> TRANSCRIBING
    S-->>UI: StateChanged "Transcribing..."
    S->>W: submit(_process_turn)
    W->>R: stop() (0.3 s post-roll)
    R-->>W: AudioClip (native sample rate, up to 2 channels)
    W->>W: prepare_for_stt: mono, min 0.25 s, peak >= 0.01, resample to 16 kHz, peak-normalise to 0.95
    alt too short or too quiet
        W-->>UI: StateChanged IDLE "Too short or too quiet, try again"
    else audio accepted
        W->>STT: transcribe(audio_16k)
        STT-->>W: Transcript (raw Whisper text)
        alt empty text
            W-->>UI: StateChanged IDLE "Didn't catch that, try again"
        else text found
            W-->>UI: UserSaid(raw transcript)
            W-->>UI: StateChanged THINKING
            W->>LLM: reply(history, raw)
            Note over LLM: POST /api/chat with TURN_SYSTEM_PROMPT, last 6 exchanges, raw text, format = TURN_SCHEMA
            LLM-->>W: TutorReply (reply + errors[])
            W->>W: filter_corrections(raw, errors)
            W->>W: pick_live(corrections) -> live major or none
            W->>W: store Turn, history.add_exchange(raw, reply)
            W-->>UI: TutorSaid(reply, live correction)
            opt TTS available
                W-->>UI: StateChanged SPEAKING
                W->>TTS: speak("Quick tip: ... " + reply)
            end
            W-->>UI: StateChanged IDLE "Ready"
        end
    end
```

Step notes:

- **Raw transcript.** `Transcript.text` is joined from the Whisper segments and stripped, nothing more. The same string goes to the chat bubble (`UserSaid`), to `Turn.user_text`, to the language-model request and to the history.
- **Request payload** (`OllamaTutorModel._chat`): `model`, `messages` (system prompt, history, user text), `stream: false`, `format` (the JSON schema), `options` (`temperature`, `num_ctx: 4096`) and `keep_alive: "10m"`. Timeouts are 5 s to connect and `TUTOR_OLLAMA_TIMEOUT` seconds to read.
- **Parsing.** The answer is parsed leniently: strict JSON first, then the first balanced `{...}` object, then the raw text as the reply with no corrections. Individual invalid error items are skipped.
- **Memory.** The history stores the learner's raw text and only the tutor's `reply` string (not the JSON, not the correction). It keeps the last `TUTOR_HISTORY_EXCHANGES` pairs (default 6); `0` disables memory.
- **Spoken text.** When there is a live correction, the spoken text is `Quick tip: instead of '<original>', say '<corrected>'.` followed by the reply. The chat shows the reply bubble and, after it, a separate correction card.
- **Failure branches.** If Ollama is unreachable or times out, `ErrorRaised` is emitted, the state returns to `IDLE` and the turn is not stored (the learner's bubble stays on screen). Transcription or recording errors behave the same way. See [architecture.md](architecture.md#failure-recovery).
- **Level meter.** While recording, the PortAudio callback sends `LevelChanged` events directly to the window queue (not through the worker).

## End-of-session report

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as TutorWindow (Tk thread)
    participant S as ConversationSession
    participant W as SerialWorker (worker thread)
    participant LLM as OllamaTutorModel
    participant TTS as PiperSynthesizer

    User->>UI: click "End session"
    UI->>S: end_session()
    S->>S: IDLE -> REPORTING (ignored in any other state)
    S-->>UI: StateChanged "Writing feedback..."
    S->>W: submit(_build_report)
    W->>W: collect corrections of all turns
    W->>W: dedupe majors and minors (same original and corrected text)
    alt at least one turn
        W->>LLM: feedback(turns)
        Note over LLM: POST /api/chat with REPORT_SYSTEM_PROMPT and "Learner said / Recorded errors" (last 40 turns), format = REPORT_SCHEMA
        LLM-->>W: SessionFeedback (summary, strengths, focus_areas)
    else no turns
        W->>W: no LLM call, empty report
    end
    W-->>UI: ReportReady(SessionReport)
    opt feedback summary available
        W->>TTS: speak(summary)
    end
    W->>W: clear turns and history
    W-->>UI: StateChanged IDLE "Ready"
```

Step notes:

- `SessionReport` carries `turn_count`, the deduplicated `major_errors` and `minor_errors`, the `feedback` and, if feedback generation failed, a `feedback_error` text. The recorded errors are shown even when the feedback call fails.
- The report text in the chat has the sections `Major errors`, `Minor errors` (each line `"original" -> "corrected" (explanation)`), then `Feedback:` with the summary, `+` lines for strengths and `> Focus on:` lines for focus areas.
- Only the summary is spoken. After the report the turns and the history are cleared, so the next conversation starts fresh.
- With zero turns the chat shows `No turns were recorded in this session.`
