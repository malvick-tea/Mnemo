# Anki cards

Mnemo generates spaced-repetition cards from any note via the LLM. v1
delivers cards as a Telegram message you copy into Anki manually;
direct AnkiConnect push lands in milestone-3.

## Triggering

- **Inline button:** tap **🎴 Anki** on any note message.
- **Slash command:** `/anki <short_id>` — the 8-char ID is shown under
  each note (`[3f1c2d8e]`).
- **HTTP:** `POST /v1/notes/{note_id}/anki` returns
  `{ "note_id", "cards": [...], "model_used" }`.

## Card types

- **basic** — `{ "type": "basic", "front": "...", "back": "..." }`
- **cloze** — `{ "type": "cloze", "text": "Postgres uses {{c1::MVCC}} for isolation." }`

## How the LLM is prompted

See `services/api/src/mnemo_api/llm/prompts/anki_cards_v1.jinja2`. The
model is asked to return JSON only with 3-8 cards. Vague notes
(opinions, TODOs) return `{"cards": []}` and the bot replies "No cards
generated — the note may be too short or non-factual."

## Validation

Cards are dropped if they fail any of:
- missing `front` or `back` (basic)
- `cloze` text without a `{{cN::...}}` marker
- non-string `type` field
- batch exceeds 20 cards (we truncate)

## Limitations

- No direct AnkiConnect push yet. v2 will add an `anki_connect_url`
  field to the integration config and a worker that posts to
  `/api/note/addNotes`.
- We never check for duplicates against existing decks — re-generating
  the same note's cards will produce semantically-equivalent duplicates
  that Anki will warn you about on import.
