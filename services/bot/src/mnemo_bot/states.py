"""FSM groups."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class QueryFlow(StatesGroup):
    """Rolling 5-minute conversational window so 'what about X?' carries
    context. Stored in Redis-backed FSMContext storage."""

    in_thread = State()
