# AI pipeline

Both AI steps live in `api/app/ai/` and go through one helper, `structured_call`
(`api/app/ai/claude.py`). It sends a single request to Claude with
[structured outputs](https://platform.claude.com/docs) and gets back a Pydantic model that has
already been validated.

| Setting | Default | Meaning |
|---|---|---|
| `CLAUDE_MODEL` | `claude-opus-5-5` | Model for both steps |
| `RECONSTRUCT_EFFORT` | `high` | Effort for reading boards (dense handwriting benefits from more thinking) |
| `SUMMARY_EFFORT` | `medium` | Effort for writing recaps |

Requests opt into **server-side refusal fallbacks** (`fallbacks: "default"`). If a safety
classifier declines a request, the API retries it on a fallback model inside the same call.
A refusal that still remains is stored on the board or lesson as a readable error.

## 1. Board reconstruction

`reconstruct(file_name)`:

1. The stored PNG is downscaled to a long edge of 1568 px for the model.
2. Claude receives the image, its size, and a system prompt that defines the five element kinds.
3. The response is validated against `Scene` (`api/app/ai/scene.py`) and scaled back to
   full-resolution coordinates.

The model answers with a `VisionScene` (`api/app/ai/vision.py`), whose vocabulary follows how
the real boards were used: sticky-note grids, block arrows as pointers, attached connectors, code,
regions kept as pictures, and frames for collages. See [Importing boards](boards.md). Every
element kind is tagged with an enforced single-value enum, so the model can't invent new kinds.
Text is transcribed exactly as written, in the original language and script.

draw.io boards never reach this step: they are imported exactly and for free.

## 2. Lesson summary

`summarize(lesson, student_name, language)` builds the material from the lesson title, the tutor's
notes and every board's `transcript`. It asks for a `LessonSummary`:

| Field | Use |
|---|---|
| `headline`, `topics` | Lesson list and email subject |
| `key_points`, `formulas`, `exercises` | Recap panel |
| `recap_message` | The friendly message the student receives |
| `review_suggestions` | "Before next lesson" practice |

The prompt forbids inventing topics that aren't on the boards or in the notes.

## Mock mode

When `ANTHROPIC_API_KEY` is empty, `mock_scene` and `mock_summary` return deterministic sample
data. The demo, the tests and offline development all use this mode.

## Cost notes

- One board means one vision request. A recap means one text-only request over the transcripts,
  never the images.
- Effort is the main cost lever. Lowering `RECONSTRUCT_EFFORT` to `medium` is worth measuring
  on real boards before changing the default.
