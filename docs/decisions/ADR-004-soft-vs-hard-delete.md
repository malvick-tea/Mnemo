# ADR-004: Hard-delete notes for v1

- **Status:** accepted
- **Date:** 2026-02-08

## Context

A `DELETE /v1/notes/{id}` user action could be implemented as:
1. **Soft delete** — set `deleted_at`, keep the row + chunks + Qdrant points.
2. **Hard delete** — actually drop the row, cascade chunks, remove Qdrant points.

## Decision

For Phase 1 we hard-delete. The endpoint:
- removes the row from `notes` (ON DELETE CASCADE drops `chunks`, `note_tags`);
- enqueues a worker task to remove the corresponding Qdrant points.

## Consequences

**Good:**
- Simple mental model — "deleted means gone" matches user intuition.
- No drift between Postgres and Qdrant counts of "live" content.
- No accidental leak of "deleted" data into RAG answers.

**Trade-off:**
- No undo. If a user fat-fingers, they lose the note. This is acceptable
  for v1 because the bot's only delete entrypoint is an inline button
  with a confirmation step (TODO: confirmation prompt — Phase 1.1).
- Backups become the only recovery path.

## Alternatives considered

- **Soft delete** — would have been nice for undo, but doubles the
  filter complexity on every query (`WHERE deleted_at IS NULL`) and we
  don't have a UI surface for restore.
- **Trash with TTL** — postpone to Phase 2 with a "🗑 Recently deleted"
  section in the bot.
