# Tutor behavior

This page describes what the tutor does with your speech: how it is transcribed, which mistakes get corrected, what is shown versus spoken, and what to expect from a small local model.

## Literal transcription

The transcript in the chat is Whisper's raw output. If you say "Hi - Could you hear me?", the app must not turn it into "Can you hear me?". Nothing after Whisper (code or language model) rewrites the text: it goes unchanged to the chat bubble, to the stored turn, to the model request and to the history.

Whisper is called (`adapters/whisper_stt.py`, `build_transcribe_kwargs`) with these options:

| Option | Value | Why |
| --- | --- | --- |
| `language` | `"en"` | No language detection step |
| `task` | `"transcribe"` | Never translate |
| `beam_size` | `TUTOR_WHISPER_BEAM_SIZE` (5) | Accuracy / speed trade-off |
| `temperature` | `0.0` | Greedy, deterministic decoding |
| `condition_on_previous_text` | `False` | The previous turn must not steer the next one |
| `initial_prompt` | `None` | A prompt of "correct" English would bias the output towards it |
| `hotwords` | `None` | No vocabulary bias |
| `without_timestamps` | `True` | Not needed |
| `word_timestamps` | `False` | Not needed |
| `suppress_blank` | `True` | Pinned explicitly |
| `suppress_tokens` | `[-1]` | Pinned explicitly |
| `multilingual` | `False` | English only |
| `no_speech_threshold` | `0.6` | Pinned explicitly |
| `log_prob_threshold` | `-1.0` | Pinned explicitly |
| `compression_ratio_threshold` | `2.4` | Pinned explicitly |
| `vad_filter` | `True` | Skip silence between phrases |
| `vad_parameters` | `{"min_silence_duration_ms": 500, "speech_pad_ms": 400}` | Voice activity detection settings |

The segment texts are joined with `"".join(...)` and stripped. Only an empty result is dropped (`Didn't catch that, try again`); short transcripts such as "Hi there" are kept.

### Honest limits of Whisper

Whisper is a language model for speech, not a phonetic recorder. No decoding flag turns that off. Expect:

- It **adds punctuation and capitalisation**.
- It **usually drops fillers** such as "um" and "uh".
- It **may smooth false starts** and repetitions.
- It may **nudge ungrammatical speech towards likely English** (for example "he go" can come back as "he goes"), which hides some errors from the tutor.

The one known lever that encourages disfluent or verbatim output is an `initial_prompt` containing such text. It is **intentionally not used**, because it would put "expected" text in front of the decoder, which conflicts with the goal of an unbiased transcript.

## Correction policy

The tutor model receives your raw text and must answer with JSON containing a `reply` and a list of `errors`, each with `original`, `corrected`, `explanation` and `severity` (`major` or `minor`). The schema is sent to Ollama as the structured-output `format`.

| Severity | Meaning (from the prompt) | What happens |
| --- | --- | --- |
| `major` | A mistake a native speaker would clearly notice or that makes the meaning unclear: wrong verb tense, subject-verb agreement, word order, wrong or missing auxiliary, a wrong word that changes the meaning | The first major error of the turn is shown and spoken live |
| `minor` | A small slip that does not affect understanding: a missing article, a small preposition slip, slightly unnatural wording | Recorded silently for the end-of-session report |

The prompt tells the model that punctuation, capitalisation, spelling, filler words, repetitions, false starts, contractions and normal informal speech are **not** errors, and that "if you are not sure, it is NOT an error".

### Guards in code

The model's output is not trusted blindly. `domain/corrections.py` applies these rules to every turn:

1. **Cosmetic-only corrections are dropped.** Both texts are normalised (lower-case, punctuation removed except apostrophes, spaces collapsed). If `original` and `corrected` are equal after that, the item is discarded. Example: "Hi" -> "Hi," is not a correction.
2. **Invented corrections are dropped.** The normalised `original` must appear, as whole words, inside the normalised transcript. Otherwise the model quoted something you did not say and the item is discarded.
3. **Empty items are dropped** (empty `original` or `corrected`). Items with a missing field or an unknown severity are skipped while parsing.
4. **At most one live correction.** `pick_live` takes the first `major` item. Any other major items and all minor items stay recorded silently, even though the schema allows several.
5. **Duplicates are merged** in the report (same normalised original and corrected text).

The code does **not** check that a `corrected` phrase is actually right, and it does not re-classify severity; those depend on the model.

## What is shown, what is spoken

| Item | Chat | Voice |
| --- | --- | --- |
| Your transcript | `You: <raw text>` | no |
| Tutor reply | `Alex: <reply>` | yes |
| Live correction (one major error) | Highlighted card: `Tip: "<original>"  ->  "<corrected>"` and the explanation | `Quick tip: instead of '<original>', say '<corrected>'.` is spoken **before** the reply, so the follow-up question is heard last |
| Minor errors, extra major errors | not shown | no |
| Session report | Full report | Only the summary |

Without Piper the same content appears in the chat and nothing is spoken.

The reply is asked to be one to three short sentences, plain text (no lists, emojis or markdown, because it is read aloud), always ending with one follow-up question, and never to mention your mistakes.

## End-of-session report

Clicking **End session** (only possible when idle) sends the learner's raw sentences and the recorded errors of the last 40 turns to the model with a second prompt. The chat then shows:

- `Major errors` and `Minor errors`, deduplicated, each line as `"original" -> "corrected" (explanation)`, or `none`.
- `Feedback:` summary (3 to 5 sentences addressed to "you"), `+` strengths (1 to 3) and `> Focus on:` points (1 to 3, based only on the recorded errors).
- If feedback could not be generated: `Feedback unavailable: <reason>`, with the error lists still shown.
- With no turns: `No turns were recorded in this session.`

The report prompt says to avoid mentioning punctuation, capitalisation and spelling because the text comes from speech recognition.

## Prompts

Both prompts are defined in [`src/english_tutor/domain/prompts.py`](../src/english_tutor/domain/prompts.py) as `TURN_SYSTEM_PROMPT` and `REPORT_SYSTEM_PROMPT`. They are quoted here as they stand in the code; the source file is authoritative. The earlier custom Ollama model `english-teacher` is no longer used.

### Turn prompt

```text
You are Alex, a friendly English conversation partner. The learner is practicing SPOKEN English.
Their messages are automatic speech-to-text transcripts.

YOUR REPLY ("reply"):
- Respond naturally to WHAT the learner said, like a friend in a real conversation.
- 1 to 3 short sentences, simple everyday English. No lists, no emojis, no markdown (your reply is read aloud).
- Always end with ONE follow-up question about the topic.
- Never talk about the learner's mistakes in "reply". Corrections go only in "errors".

ERRORS ("errors"):
- "major": a mistake a native speaker would clearly notice, or one that makes the meaning unclear:
  wrong verb tense ("yesterday I go"), subject-verb agreement ("he don't"), wrong word order,
  wrong or missing auxiliary ("you are agree"), wrong word that changes the meaning.
- "minor": small slips that do not affect understanding: a missing article, a small preposition slip,
  slightly unnatural wording.
- NOT errors, never report them: punctuation, capitalization, spelling, filler words (um, uh),
  repetitions, false starts, contractions, normal informal speech ("gonna", "Could you hear me?").
- If you are not sure, it is NOT an error. Most messages have no errors: return an empty list.
- "original": copy the exact words from the learner's message. "corrected": the same phrase, fixed,
  as short as possible. "explanation": one short, simple sentence.

Answer ONLY with JSON: {"reply": "...", "errors": [{"original": "...", "corrected": "...", "explanation": "...", "severity": "major" or "minor"}]}

Examples:
Learner: Hi. Could you hear me?
{"reply": "Yes, I can hear you perfectly! How is your day going so far?", "errors": []}
Learner: yesterday I go to the park with my sister
{"reply": "That sounds lovely! What did you two do at the park?", "errors": [{"original": "I go", "corrected": "I went", "explanation": "Use the past tense for yesterday.", "severity": "major"}]}
Learner: I live in the Buenos Aires since five years
{"reply": "Five years is a long time! What do you like most about living there?", "errors": [{"original": "since five years", "corrected": "for five years", "explanation": "Use 'for' with a length of time.", "severity": "major"}, {"original": "the Buenos Aires", "corrected": "Buenos Aires", "explanation": "City names don't take 'the'.", "severity": "minor"}]}
```

Message order for each turn: this system prompt, then the stored history (up to `TUTOR_HISTORY_EXCHANGES` pairs), then your raw text as the user message.

### Report prompt

```text
You are an encouraging English teacher writing end-of-session feedback for a learner who practiced
spoken English. You receive what the learner said and the list of errors recorded during the session.
- "summary": 3 to 5 sentences, speaking directly to the learner ("you"). Be warm and honest.
- "strengths": 1 to 3 short points about what went well.
- "focus_areas": 1 to 3 short, practical points, based ONLY on patterns in the recorded errors.
- Do not invent errors that are not in the list. Never mention punctuation, capitalization or spelling
  (the text comes from speech recognition).
- If there are no recorded errors, say so and suggest one way to stretch (richer vocabulary, longer answers).
Plain text only inside the JSON fields. Answer ONLY with JSON:
{"summary": "...", "strengths": ["..."], "focus_areas": ["..."]}
```

The user message is built by `build_report_user_message`:

```text
Learner said:
1. <raw transcript of turn 1>
2. ...

Recorded errors:
- [major] "<original>" -> "<corrected>": <explanation>
- ...
```

with `none` under `Recorded errors:` when the list is empty.

### Output schemas

`TURN_SCHEMA`: object with required `reply` (string) and `errors` (array of objects with required `original`, `corrected`, `explanation` strings and `severity` in `["major", "minor"]`). `REPORT_SCHEMA`: object with required `summary` (string), `strengths` and `focus_areas` (arrays of strings).

If the model still returns something unparseable, the raw text is used as the reply with no corrections (or as the summary, for the report). If even that is empty, the app uses `Sorry, I lost my train of thought. Could you say that again?` or `I could not write the feedback this time.`

## Known limits of an 8B model

The default model is `llama3:8b-instruct-q4_K_M`, a 4-bit 8-billion-parameter model. In a manual test with Ollama 0.16.2:

- It **can miss errors**. For example "we watch" and "since five years" were not flagged, and "I am living ... since five years" and "every weekends" were recorded only as minor.
- "Hi. Could you hear me?" was correctly left uncorrected, and "Yesterday I go" produced a live major correction (`I go` -> `I went`).
- **First reply after start-up can take about 40 seconds** while Ollama loads the model into memory. Later replies took about 1.5 to 2 seconds on an RTX 3090. The model stays loaded for 10 minutes after the last request (`keep_alive`).
- Because Whisper may already smooth some errors (see above), a missing correction is not always the model's fault.

Treat the tutor as a conversation partner with a safety net, not as an exam grader.

## Using a bigger model

1. Pull the model: `ollama pull <model-name>`.
2. Point the app at it:

   ```powershell
   $env:TUTOR_OLLAMA_MODEL = "<model-name>"
   english-tutor
   ```

The app checks at start-up that the exact name is installed. A bigger model may catch more errors, at the cost of more memory and slower replies; raise `TUTOR_OLLAMA_TIMEOUT` if replies time out. The model must support Ollama's structured outputs (`format` with a JSON schema); the default was tested that way, other models were not tested here.
