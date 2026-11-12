# Data flow

This page follows the data through the application for the main use cases. For the structure behind it see [architecture.md](architecture.md); for the rules applied to corrections see [tutor-behavior.md](tutor-behavior.md).

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
    participant LOG as ConversationLog
    participant BOOK as MistakeBook
    participant TTS as PiperSynthesizer
    participant UI as TutorWindow (Tk thread)

    User->>KB: hold PTT key (default Right Ctrl)
    KB->>S: on_ptt_press()
    S->>S: IDLE -> RECORDING
    S-->>UI: StateChanged "Listening..."
    S->>W: submit(_start_recording)
    W->>R: start(device_index)
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
            W->>LOG: record YOU, raw transcript
            W-->>UI: StateChanged THINKING
            W->>LLM: reply(history, raw)
            Note over LLM: POST /api/chat with TURN_SYSTEM_PROMPT, last 6 exchanges, raw text, format = TURN_SCHEMA
            LLM-->>W: TutorReply (reply + errors[])
            W->>W: filter_corrections(raw, errors)
            W->>W: pick_live(corrections) -> live major or none
            W->>W: store Turn, history.add_exchange(raw, reply)
            W-->>UI: TutorSaid(reply, live correction)
            W->>LOG: record ALEX, reply (and TIP when there is a live correction)
            opt at least one correction kept
                W->>BOOK: add_corrections(corrections, raw)
                BOOK->>BOOK: group by normalised pair, save mistakes.json
                W-->>UI: MistakesChanged(ranked records)
            end
            opt TTS available
                W-->>UI: StateChanged SPEAKING
                W->>TTS: speak("Quick tip: ... " + reply)
            end
            W-->>UI: StateChanged IDLE "Ready"
        end
    end
```

Step notes:

- **Microphone on the worker.** The key-hook thread only flips the state and queues jobs. Opening the microphone (`_start_recording`) and closing it (`_process_turn`) both run on the worker, in queue order. If the release arrives before the start job runs, the start is skipped and the turn ends with `Too short or too quiet, try again`. If opening fails, `Could not start recording: ...` is shown and the state returns to `IDLE`.
- **Raw transcript.** `Transcript.text` is joined from the Whisper segments and stripped, nothing more. The same string goes to the chat bubble (`UserSaid`), the log (`YOU`), `Turn.user_text`, the language-model request, the history and the mistake examples.
- **Logging.** The `YOU` line is written before the tutor is called, so it exists even if Ollama fails. Log and mistake-history failures are caught: they produce a one-time notice and a console warning, never a failed turn.
- **Mistake update.** Every correction that survived `filter_corrections` (major and minor, not just the live one) is counted in the mistake book, which saves `data/mistakes.json` atomically and sends `MistakesChanged` so the Mistakes tab refreshes.
- **Request payload** (`OllamaTutorModel._chat`): `model`, `messages` (system prompt, history, user text), `stream: false`, `format` (the JSON schema), `options` (`temperature`, `num_ctx: 4096`) and `keep_alive: "10m"`. Timeouts are 5 s to connect and `TUTOR_OLLAMA_TIMEOUT` seconds to read.
- **Parsing.** The answer is parsed leniently: strict JSON first, then the first balanced `{...}` object, then the raw text as the reply with no corrections. Individual invalid error items are skipped.
- **Memory.** The history stores the learner's raw text and only the tutor's `reply` string (not the JSON, not the correction). It keeps the last `TUTOR_HISTORY_EXCHANGES` pairs (default 6); `0` disables memory.
- **Spoken text.** When there is a live correction, the spoken text is `Quick tip: instead of '<original>', say '<corrected>'.` followed by the reply. The chat shows the reply bubble and, after it, a separate correction card.
- **Failure branches.** If Ollama is unreachable or times out, `ErrorRaised` is emitted, the state returns to `IDLE` and the turn is not stored (the learner's bubble and log line remain). Transcription or recording errors behave the same way. See [architecture.md](architecture.md#failure-recovery).
- **Level meter.** While recording, the PortAudio callback sends `LevelChanged` events directly to the window queue (not through the worker).

## One practice turn

Practice starts from the Mistakes tab. The drill has its own bounded history (4 exchanges) and uses a different system prompt ([tutor-behavior.md](tutor-behavior.md#practice-mode)).

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as TutorWindow (Tk thread)
    participant S as ConversationSession
    participant W as SerialWorker (worker thread)
    participant C as OllamaTutorModel (PracticeCoach)
    participant LOG as ConversationLog
    participant BOOK as MistakeBook
    participant TTS as PiperSynthesizer

    User->>UI: click Practice on a mistake row
    UI->>S: start_practice(key)
    S->>S: IDLE -> THINKING (only if no drill is active)
    S-->>UI: StateChanged "Preparing practice..."
    S->>W: submit(_open_practice)
    W->>BOOK: get(key)
    W->>C: practice(target, [], "START")
    Note over C: POST /api/chat with PRACTICE_SYSTEM_PROMPT + TARGET block, format = PRACTICE_SCHEMA
    C-->>W: PracticeReply (feedback + next_prompt)
    W-->>UI: PracticeChanged(target)
    W-->>UI: TutorSaid(feedback + next_prompt)
    W->>LOG: record PRACTICE "Started: ..." and ALEX
    W->>TTS: speak(feedback + next_prompt)
    W-->>UI: StateChanged IDLE "Practice: hold Right Ctrl to answer"

    User->>S: hold PTT key, speak, release (same recording path as a normal turn)
    W->>W: transcribe, UserSaid(raw), record YOU
    W-->>UI: StateChanged THINKING "Checking your answer..."
    W->>C: practice(target, drill history, raw)
    C-->>W: PracticeReply (outcome, feedback, next_prompt)
    opt parsed and outcome is correct or incorrect
        W->>BOOK: add_practice(key, outcome)
        W-->>UI: MistakesChanged(ranked records)
    end
    W-->>UI: PracticeFeedback(outcome, feedback, next_prompt)
    W->>LOG: record PRACTICE "[outcome] feedback" and ALEX next_prompt
    W->>TTS: speak(feedback + next_prompt)
    W-->>UI: StateChanged IDLE "Practice: hold Right Ctrl to answer"

    User->>UI: click Stop practice
    UI->>S: stop_practice()
    S-->>UI: PracticeChanged(None), StateChanged IDLE "Ready: hold Right Ctrl"
    S->>W: submit(log "Stopped practice")
```

Step notes:

- Recording, Whisper and the log line for the learner's answer are identical to a normal turn; the difference starts after `UserSaid`: the transcript goes to `practice()` instead of `reply()`.
- The normal correction pipeline is skipped: no `filter_corrections`, no `Turn` is stored, the normal chat history is not touched, nothing is added to the session report, and no new mistakes are recorded from a practice answer.
- The drill history stores each answer together with the spoken feedback and next question. A failed coach call leaves it unchanged and the drill stays active.
- An unparseable coach answer is treated as `not_used` with the raw text as the next question, and does not change the practice score.
- In the chat, the verdict appears as `Correct! <feedback>` or `Try again: <feedback>` (or the plain feedback for `not_used`), followed by the next question as a tutor bubble.

## End-of-session report

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as TutorWindow (Tk thread)
    participant S as ConversationSession
    participant W as SerialWorker (worker thread)
    participant LLM as OllamaTutorModel
    participant LOG as ConversationLog
    participant TTS as PiperSynthesizer

    User->>UI: click "End session"
    UI->>S: end_session()
    S->>S: IDLE -> REPORTING (ignored in any other state or during a drill)
    S-->>UI: StateChanged "Writing feedback..."
    S->>W: submit(_build_report)
    W->>W: make_report: collect corrections of all turns
    W->>W: dedupe majors and minors (same original and corrected text)
    alt at least one turn
        W->>LLM: feedback(turns)
        Note over LLM: POST /api/chat with REPORT_SYSTEM_PROMPT and "Learner said / Recorded errors" (last 40 turns), format = REPORT_SCHEMA
        LLM-->>W: SessionFeedback (summary, strengths, focus_areas)
    else no turns
        W->>W: no LLM call, empty report
    end
    W-->>UI: ReportReady(SessionReport)
    W->>LOG: record REPORT, then new_session()
    opt feedback summary available
        W->>TTS: speak(summary)
    end
    W->>W: clear turns and history
    W-->>UI: StateChanged IDLE "Ready"
```

Step notes:

- `SessionReport` carries `turn_count`, the deduplicated `major_errors` and `minor_errors`, the `feedback` and, if feedback generation failed, a `feedback_error` text. The recorded errors are shown even when the feedback call fails.
- The report is built from the session's conversation turns only, so practice answers never appear in it.
- The report text in the chat has the sections `Major errors`, `Minor errors` (each line `"original" -> "corrected" (explanation)`), then `Feedback:` with the summary, `+` lines for strengths and `> Focus on:` lines for focus areas. The same text is written to the log under `REPORT`.
- `new_session()` makes the next logged entry start a new `.log` file.
- Only the summary is spoken. After the report the turns and the chat history are cleared, so the next conversation starts fresh. The persistent mistake history is **not** cleared.
- With zero turns the chat shows `No turns were recorded in this session.`
