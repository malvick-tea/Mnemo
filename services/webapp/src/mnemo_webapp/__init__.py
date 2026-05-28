"""Mnemo admin webapp — minimal FastAPI + HTMX UI.

This is the **Phase 4 placeholder** referenced in ARCHITECTURE.md and
PLAN.md. It surfaces notes, queries, and tags in a browser without
duplicating the bot's logic. Authentication is delegated to the reverse
proxy (Caddy basicauth) per ADR-001's "deploy-time" auth split.
"""

__version__ = "0.1.0"
