# Anki cards

The `007-anki-generate` workflow turns a Mnemo note into spaced-repetition
cards via the [AnkiConnect](https://foosoft.net/projects/anki-connect/)
add-on.

## Setup

1. Install AnkiConnect (Tools → Add-ons → 2055492159 in Anki).
2. Make AnkiConnect reachable from the n8n container. Easiest: run Anki on
   the same machine as Mnemo and set `ANKI_CONNECT_URL=http://host.docker.internal:8765`.
3. Enable the integration in `/settings`.

## Triggering

From the bot, on any note: tap **🃏 Anki** in the inline keyboard (added in
milestone-3). Or call:

```bash
curl -X POST https://your.mnemo.example.com/v1/integrations/anki/generate \
  -H 'Authorization: Bearer …' \
  -d '{"note_id": "..."}'
```

The workflow asks the LLM (`anki_cards_v1.jinja2` prompt) to produce 3-8
cards, then `addNotes`s them to the deck configured in your `/settings`.

## Card types

- **basic** — front/back.
- **cloze** — `{{c1::masked}}` syntax. Anki must have the Cloze note type
  installed (it's a default).

## Limitations

- We never overwrite an existing card. If you re-generate, you'll get
  duplicates — Anki's duplicate detection will warn you.
- Vague notes (opinions, TODOs) return `{"cards": []}` and the bot will
  reply "nothing testable here".
