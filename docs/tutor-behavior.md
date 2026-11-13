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
| `word_timestamps` | `False` | With `True`, faster-whisper 1.2.1 re-decodes the audio after the last word and can repeat or invent words at the end; [long pauses](#long-pauses) are timed separately |
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

The tutor model receives your raw text and must answer with JSON containing a `reply` and a list of `errors`, each with `original`, `corrected`, `explanation`, `severity` (`major` or `minor`) and `category`. The schema is sent to Ollama as the structured-output `format`.

**Categories.** `category` is one of `verb_tense`, `agreement`, `articles`, `prepositions`, `word_order`, `word_choice`, `false_friend`, `plural`, `pronoun`, `other` (an enum in the schema). The parser lowercases the value, turns spaces and hyphens into underscores, and maps anything unknown or missing to `other`. Long pauses get `fluency`, assigned by the app, never by the model. The category is stored with the mistake (a later correction with a category replaces an older one), counted in the session statistics, shown in the report as `Most frequent: prepositions (4), verb tense (3)` (the top three; `other` and `fluency` are not listed) and used by the category filter of the Mistakes tab. It is a label from a small model: it is not checked by the code.

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

## Pronunciation hints

The word timings used for [long pauses](#long-pauses) also carry how sure the recogniser was of each word (its probability, 0 to 1). Words under **0.35**, with at least 3 letters, are collected per turn and listed once in the report as `Check your pronunciation (the recogniser was unsure about): ...`. They are hints: never stored in the mistake history, never counted as errors, never sent to the model. They exist only when **Track long pauses** is on, because that switch is what asks for word timings.

Known limits. The timings are a forced alignment of text Whisper already decoded, so its confidence stays high even in clear trouble: in a test with synthetic speech, 0 dB and -6 dB of added noise, no word went under 0.61. The threshold is deliberately low to avoid false alarms; it has not been tuned with real learner recordings and may rarely trigger. A low value can also come from noise or the microphone, which is why the text says "the recogniser was unsure" and not "you mispronounced".

## Role-play scenarios

The **Scenario** drop-down in the main window (enabled when the app is idle, not practising and before your first answer of the session) picks one of: free conversation (default), job interview, restaurant, doctor's appointment, airport, small talk, team meeting. Picking one makes Alex say a fixed opening line (shown, spoken and logged as `ALEX:`) and adds a `SCENARIO (role-play)` section to the **turn** prompt only: who Alex plays, the opening line already said, and the reminder that the role never changes how mistakes are reported. The report and practice prompts are unchanged.

Rules enforced by the code (`domain/scenarios.py`): the section is empty for the free conversation and for unknown keys; the scenario returns to free when the session ends (the drop-down follows); the scenario key is stored in the session statistics. The report adds `Useful for this situation (not used yet): ...` with up to 6 key phrases of the scenario that none of your sentences contained. Matching is on whole words after normalising (case and punctuation ignored), so `menus` does not count as `menu`; it is a hint, not a test. Whether the 8B model keeps the role is up to the model.

## Natural phrasing

Besides `errors`, the tutor answers with a `natural` string. It is filled only when the sentence has **no** error but a native speaker would clearly say it differently (stiff or translated-from-Spanish wording); otherwise it is empty. The app shows it as `More natural: "..."` below the reply when **Settings > General > Suggest more natural phrasing** is on (read on every turn, no restart).

Rules enforced by the code (`pick_natural`): it is dropped when the turn has any real correction, when it is empty, and when it only repeats the learner's sentence (ignoring case and punctuation). It is never spoken, never stored in the mistake history or the statistics, and it is written to the conversation log as `NATURAL`. Whether a sentence "sounds unnatural" is the model's opinion; an 8B model also misses some real errors, so treat the suggestion as a hint.

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
| English level | Adds the level line to the `LEARNER` section of every prompt (turn, report, practice) and, at A2, makes Piper speak about 15 % slower (`length_scale` 1.15). **Repeat** and **Slower** say the tutor's last words again (Slower multiplies the pace by 1.35). Nothing else changes: mistakes are still judged by the same rules |
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
- `Long pauses` and `Slow starts` when there were any (see [Long pauses](#long-pauses)); they are not errors.
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
- Each result also moves the item's review date (spaced repetition): `correct` climbs one step of the 1 / 3 / 7 / 14 / 30-day ladder, `incorrect` goes back to 1 day, `not_used` changes nothing. Making the mistake again in conversation resets it to 1 day. Items without a schedule (stored by an older version) are treated as due. **Review due items** in the Mistakes tab starts the most overdue one, skipping the item practised last when another is due.
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

## Long pauses

A long pause is a sign that a phrase is hard for you to say. It is **not an error**: it never appears under `Major errors` or `Minor errors` and never changes how the tutor corrects you. Turn it off with **Settings > General > Track long pauses** (on by default; the next turn after **Save** uses the new value).

**How it is measured.** After the normal transcription, the finished text is force-aligned to the audio (`adapters/whisper_alignment.py`): Silero VAD (bundled with faster-whisper) finds the stretches of speech, the text is aligned to those stretches joined together (one encoder pass, no decoding), and each word is moved back to the stretch it belongs to, so the silences show up as gaps. This never changes the text, adds about 0.2 to 0.3 s per turn on a GPU (more on a CPU), and only runs while tracking is on. Asking Whisper for word timestamps while decoding was rejected because it changed the transcript (see the table above). The recording starts when the microphone opens after you press the push-to-talk key, so the first word's start time is how long you took to begin. Thresholds are fixed in `src/english_tutor/domain/hesitation.py`:

| Kind | Rule | Where it goes |
| --- | --- | --- |
| Pause inside a sentence | 1.2 s or more between two words | **Mistakes** tab as a `PAUSE` item, the conversation log (`PAUSE`), the report |
| Slow start | 3.0 s or more before the first word | Only the report, with the tutor question you were answering |

A pause item stores two words on each side of the silence, for example `"think how's … everything" -> "think how's everything"` with `You paused 1.7 s between 'how's' and 'everything'.` Repeating the same words with a pause adds to its counter like a repeated mistake. A slow start is not stored: it says the question was hard, not which words were, and every answer starts differently. The first turn of a session has no question before it, so its start is not counted. Practice answers never add pause items.

**In the report.** After the error lists, `Long pauses (practice these phrases):` lists each pause once and `Slow starts:` lists `<seconds> s to answer "<question>"`. Both sections are left out when empty. The model also receives the pause list (see [Report prompt](#report-prompt)) and may suggest practising those phrases, but is told never to call them mistakes.

**Practising a pause item.** The coach gets a fluency target (see [Practice prompt](#practice-prompt)) and only answers `correct` (you said the phrase) or `not_used`. The app then checks the timings itself: if a pause of 1.2 s or more falls between two words of the phrase, the result becomes `incorrect` with `You said it, but you paused 1.4 seconds between 'how's' and 'everything'. Try once more, in one go.` A pause elsewhere in your answer, or a slow start, does not count against the phrase.

**Limits.** Durations are close to the real silence (a 2.0 s gap measured 2.2 to 2.4 s in tests with synthetic speech, a 3.5 s slow start 3.5 s), but the pause can be placed **one word early or late** when a word sits right at the edge of the silence; the two words of context on each side usually still show the right spot. A recording with more than 30 s of speech gets no timings. If the alignment fails for any reason, that turn records no pauses and the conversation goes on. Filler sounds (`um`, `uh`) are often left out of the transcript, so a pause filled with "um" still counts as a pause. A transcript without timings (for example from an unusual model) simply records no pauses.

## Prompts

The turn and report prompts are defined in [`src/english_tutor/domain/prompts.py`](../src/english_tutor/domain/prompts.py) as `TURN_SYSTEM_PROMPT` and `REPORT_SYSTEM_PROMPT`; the practice prompt is in [`src/english_tutor/domain/practice_prompts.py`](../src/english_tutor/domain/practice_prompts.py) as `PRACTICE_SYSTEM_PROMPT`. They are quoted here as they stand in the code; the source files are authoritative. Each prompt is followed by a `LEARNER` section built by `profile_block` in [`src/english_tutor/domain/learner.py`](../src/english_tutor/domain/learner.py), for example:

```text
LEARNER:
- Name: "Mauro". Use it now and then, not in every message.
- Pronouns: he/him. Use them whenever you refer to the learner in the third person.
- English level (CEFR): B1. Use everyday vocabulary and sentences of up to about 15 words. Report at most TWO errors per message.
```

The last line depends on **Settings > General > English level** (`LEVEL_RULES` in `learner.py`): A2 asks for very simple words and one error at most, B1 two errors, B2 up to three, C1 also subtle word-choice and register errors. The level is a request to the model, not a rule the code enforces: it does not trim the list of corrections, so an 8B model may ignore it now and then.

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

Answer ONLY with JSON: {"reply": "...", "errors": [{"original": "...", "corrected": "...", "explanation": "...", "severity": "major" or "minor", "category": "..."}]}

Examples:
Learner: Hi. Could you hear me?
{"reply": "Yes, I can hear you perfectly! How is your day going so far?", "errors": []}
Learner: yesterday I go to the park with my sister
{"reply": "That sounds lovely! What did you two do at the park?", "errors": [{"original": "I go", "corrected": "I went", "explanation": "Use the past tense for yesterday.", "severity": "major", "category": "verb_tense"}]}
Learner: I live in the Buenos Aires since five years
{"reply": "Five years is a long time! What do you like most about living there?", "errors": [{"original": "since five years", "corrected": "for five years", "explanation": "Use 'for' with a length of time.", "severity": "major", "category": "prepositions"}, {"original": "the Buenos Aires", "corrected": "Buenos Aires", "explanation": "City names don't take 'the'.", "severity": "minor", "category": "articles"}]}
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
- "Long pauses" are not errors: they show phrases the learner found hard to say. If there are any,
  you may suggest practicing them for fluency, but never call them mistakes.
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

Long pauses:
- "<words before> … <words after>"
- ...
```

with `none` under `Recorded errors:` or `Long pauses:` when the list is empty.

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

For a [long pause](#long-pauses) item the TARGET section is instead:

```text
TARGET (fluency, not a grammar mistake):
- The learner paused for a long time while saying: "<words with …>"
- Goal: say "<words>" smoothly, in one go.
- "target_used": "correct" when they said this phrase (or nearly the same words), otherwise "not_used". Never "incorrect": the app measures the pauses itself.
- Ask questions whose natural answer contains this phrase.
```

Both are followed by the `LEARNER` section.

Message order for a practice call: this system prompt, the drill history (last 4 exchanges), then the learner's raw text (or `START`).

### Output schemas

`TURN_SCHEMA`: object with required `reply` (string) and `errors` (array of objects with required `original`, `corrected`, `explanation` strings and `severity` in `["major", "minor"]` and `category` in the ten model categories) plus a required `natural` string. `REPORT_SCHEMA`: object with required `summary` (string), `strengths` and `focus_areas` (arrays of strings). `PRACTICE_SCHEMA`: object with required `target_used` (one of `correct`, `incorrect`, `not_used`), `feedback` and `next_prompt` (strings).

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
