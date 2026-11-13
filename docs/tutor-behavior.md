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
| Minor errors, extra major errors | not shown (recorded in the Mistakes tab and the log) | no |
| Session report | Full report | Only the summary |

Without Piper the same content appears in the chat and nothing is spoken.

The reply is asked to be one to three short sentences, plain text (no lists, emojis or markdown, because it is read aloud), always ending with one follow-up question, and never to mention your mistakes.

## What the settings change (and what they never do)

| Setting | Effect on the tutor |
| --- | --- |
| Interface language (English / Spanish) | Only the app's own text (buttons, labels, status messages, dates in the Mistakes tab). Alex always speaks and corrects in **English**; the report, tips, practice questions and conversation logs stay English |
| Your name and pronouns | Added to the end of every prompt (turn, report, practice) as a `LEARNER` section; the next model call after **Save** uses them. They never change how mistakes are judged |
| Sound cues | Short beeps for recording start, stop and errors. They are played on a separate audio stream and never alter, delay or replace a transcript |
| Voice output | Off means text-only replies; corrections and the report are unchanged |
| Chat font size, theme, scale, density | Presentation only |
| Ollama model, Whisper model and device | Change quality and speed; the rules in this page (literal transcription, correction guards) apply to any of them. Use **Test connection** to confirm a model is installed |
| Exports | **Export last report** writes the report text shown in the chat as Markdown; **Export mistakes** writes the mistake list as CSV. Neither is re-processed by the model |

## End-of-session report

Clicking **End session** (only possible when idle) sends the learner's raw sentences and the recorded errors of the last 40 turns to the model with a second prompt. The chat then shows:

- `Major errors` and `Minor errors`, deduplicated, each line as `"original" -> "corrected" (explanation)`, or `none`.
- `Feedback:` summary (3 to 5 sentences addressed to "you"), `+` strengths (1 to 3) and `> Focus on:` points (1 to 3, based only on the recorded errors).
- If feedback could not be generated: `Feedback unavailable: <reason>`, with the error lists still shown.
- With no turns: `No turns were recorded in this session.`

The report prompt says to avoid mentioning punctuation, capitalisation and spelling because the text comes from speech recognition.

## Practice mode

The **Mistakes** tab lists every recurring correction (see [configuration.md](configuration.md#mistake-history)). **Practice** starts a short spoken drill on one entry (the target: what you said, the correct form and the rule).

1. The coach is called with the message `START`. It says in one sentence what you will practise and asks a question meant to make you use the correct form.
2. You answer with push-to-talk. Your transcript is shown and logged exactly like a normal turn.
3. The coach judges **only the target structure** in that answer and returns three fields: `target_used`, `feedback` and `next_prompt`.

| `target_used` | Meaning | Feedback | Score |
| --- | --- | --- | --- |
| `correct` | The correct form (or the same rule with other words) was used | Brief praise | +1 attempt, +1 success |
| `incorrect` | The structure was used with the same kind of mistake | The corrected version of your sentence | +1 attempt |
| `not_used` | The structure was not used (also the answer to `START`) | A kind reminder | no change |

Rules enforced by the code:

- **General corrections are skipped.** A practice answer does not go through the normal tutor call, so no other errors are reported or recorded, no turn is stored, the normal conversation memory is untouched, and practice turns are **not** part of the end-of-session report.
- The verdict is shown as `Correct! ...` or `Try again: ...` (plain feedback for `not_used`) and the next question follows as a tutor bubble. The spoken text is the feedback followed by the next question.
- The score (`practice successes/attempts`) is saved with the mistake. If the coach answer cannot be parsed as JSON, it counts as `not_used`: the raw text becomes the next question and the score does not change.
- The drill keeps its own memory of the last 4 exchanges. **Stop practice** returns to normal conversation; **End session** is disabled while a drill is active.
- The fields of the target are cleaned before they go into the prompt: whitespace collapsed to single spaces, double quotes replaced by single quotes, at most 200 characters each.

Observed behaviour with `llama3:8b-instruct-q4_K_M` (manual test, target "I go" -> "I went"):

| Learner message | Result |
| --- | --- |
| `START` | `not_used`, a one-sentence introduction and a first question |
| "Last weekend I go ..." | `incorrect`, with the corrected sentence in the feedback |
| "Yesterday I went ..." | `correct` |
| An unrelated sentence | `not_used` |

Replies took about 1.2 seconds each. Known limit: the model's next question does not always call for the target form, so a perfectly good answer can end up as `not_used`.

## Prompts

The turn and report prompts are defined in [`src/english_tutor/domain/prompts.py`](../src/english_tutor/domain/prompts.py) as `TURN_SYSTEM_PROMPT` and `REPORT_SYSTEM_PROMPT`; the practice prompt is in [`src/english_tutor/domain/practice_prompts.py`](../src/english_tutor/domain/practice_prompts.py) as `PRACTICE_SYSTEM_PROMPT`. They are quoted here as they stand in the code; the source files are authoritative. Each prompt is followed by a `LEARNER` section built by `profile_block` in [`src/english_tutor/domain/learner.py`](../src/english_tutor/domain/learner.py), for example:

```text
LEARNER:
- Name: "Mauro". Use it now and then, not in every message.
- Pronouns: he/him. Use them whenever you refer to the learner in the third person.
```

The earlier custom Ollama model `english-teacher` is no longer used.

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

### Practice prompt

`build_practice_system_prompt(target)` sends this text followed by a newline and the target block (concatenated, never formatted):

```text
You are Alex, a friendly English tutor running a short SPEAKING drill. The learner's messages are
automatic speech-to-text transcripts. The drill practices ONE structure, described in TARGET below.

Every answer is JSON with three fields, in this order:
1. "target_used": judge ONLY the target structure in the learner's last message.
   - "correct": they used the correct form, or the same rule correctly with other words.
   - "incorrect": they used the structure but made the same kind of mistake again.
   - "not_used": they did not use the structure, or the message is START.
   If you are not sure it is wrong, it is "correct". Ignore every other mistake.
   Never judge punctuation, capitalization or spelling (the text comes from speech recognition).
2. "feedback": ONE short sentence.
   - "correct": praise briefly and say what was right.
   - "incorrect": give the corrected version of their sentence.
   - "not_used": kindly remind them to use the structure.
   - START: say in one sentence what you will practice together.
3. "next_prompt": ONE short, simple question about the learner's life (yesterday, plans, habits,
   likes) that makes them naturally use the correct form in their answer.
   Never include the answer. Never repeat a question you already asked.
Spoken English only: no lists, no emojis, no markdown.
Answer ONLY with JSON: {"target_used": "...", "feedback": "...", "next_prompt": "..."}

Example (said "I go", correct form "I went", rule: use the past tense for finished actions):
Learner: START
{"target_used": "not_used", "feedback": "Let's practice talking about the past.", "next_prompt": "Where did you go last weekend?"}
Learner: last weekend I go to the beach
{"target_used": "incorrect", "feedback": "Almost! Say: last weekend I went to the beach.", "next_prompt": "What did you eat for dinner yesterday?"}
Learner: I ate pizza with my friends
{"target_used": "correct", "feedback": "Perfect, 'I ate' is the right past form!", "next_prompt": "Who did you talk to this morning?"}
```

The target block appended after it has this shape:

```text
TARGET:
- The learner said: "<original>"
- Correct form: "<corrected>"
- Rule: <explanation>
```

Message order for a practice call: this system prompt, the drill history (last 4 exchanges), then the learner's raw text (or `START`).

### Output schemas

`TURN_SCHEMA`: object with required `reply` (string) and `errors` (array of objects with required `original`, `corrected`, `explanation` strings and `severity` in `["major", "minor"]`). `REPORT_SCHEMA`: object with required `summary` (string), `strengths` and `focus_areas` (arrays of strings). `PRACTICE_SCHEMA`: object with required `target_used` (one of `correct`, `incorrect`, `not_used`), `feedback` and `next_prompt` (strings).

If the model still returns something unparseable, the raw text is used as the reply with no corrections (or as the summary, for the report). If even that is empty, the app uses `Sorry, I lost my train of thought. Could you say that again?` or `I could not write the feedback this time.` (for practice: `Let's keep going. Tell me about your day.`)

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

Set the model in **Settings > Advanced** (restart needed) or with the variable. The app checks at start-up that the exact name is installed, and **Test connection** checks it on demand. A bigger model may catch more errors, at the cost of more memory and slower replies; raise `TUTOR_OLLAMA_TIMEOUT` if replies time out. The model must support Ollama's structured outputs (`format` with a JSON schema); the default was tested that way, other models were not tested here.
