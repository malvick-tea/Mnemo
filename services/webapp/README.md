# Webapp (admin) — Phase 4

Optional FastAPI + HTMX admin UI. Not part of MVP. The bot is the user-
facing product; this is for power-users who want to browse all their notes,
tweak settings beyond what the `/settings` menu exposes, and inspect the
RAG query log.

Status: placeholder. See PLAN.md Phase 4.

Planned routes:
- `/` — search & browse notes
- `/notes/{id}` — note detail + edit
- `/queries` — recent queries with citations & feedback
- `/settings` — full settings form
- `/integrations` — connection management
