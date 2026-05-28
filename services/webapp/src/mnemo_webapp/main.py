"""Mnemo webapp entrypoint."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select, text

from mnemo_api.db import session_factory
from mnemo_api.models import Note, NoteTag, Query, Tag

from mnemo_webapp import __version__

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app = FastAPI(title="Mnemo Admin", version=__version__)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness only: process is up. DB is checked by /readyz."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness: DB is reachable."""
    try:
        async with session_factory()() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"postgres unavailable: {exc}") from exc
    return {"status": "ready"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    async with session_factory()() as session:
        notes = (
            await session.execute(
                select(Note).order_by(desc(Note.created_at)).limit(50)
            )
        ).scalars().all()
        recent_queries = (
            await session.execute(
                select(Query).order_by(desc(Query.created_at)).limit(10)
            )
        ).scalars().all()
        tag_rows = (
            await session.execute(
                select(Tag.name, func.count(NoteTag.note_id).label("cnt"))
                .join(NoteTag, NoteTag.tag_id == Tag.id, isouter=True)
                .group_by(Tag.name)
                .order_by(desc("cnt"))
                .limit(40)
            )
        ).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "notes": notes,
            "queries": recent_queries,
            "tags": [(name, count or 0) for name, count in tag_rows],
            "version": __version__,
        },
    )


@app.get("/notes/{note_id}", response_class=HTMLResponse)
async def note_detail(request: Request, note_id: str) -> HTMLResponse:
    try:
        uid = UUID(note_id)
    except ValueError:
        return HTMLResponse("Not found", status_code=404)
    async with session_factory()() as session:
        note = await session.get(Note, uid)
        if note is None:
            return HTMLResponse("Not found", status_code=404)
        tag_names = (
            await session.execute(
                select(Tag.name)
                .join(NoteTag, NoteTag.tag_id == Tag.id)
                .where(NoteTag.note_id == note.id)
            )
        ).scalars().all()
    return templates.TemplateResponse(
        request,
        "note.html",
        {"note": note, "tags": list(tag_names), "version": __version__},
    )
