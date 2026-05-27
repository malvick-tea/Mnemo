"""Declarative base for all ORM models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

# Naming convention — keeps Alembic autogenerate stable across runs.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    type_annotation_map = {
        UUID: __import__("sqlalchemy").Uuid(as_uuid=True),
        datetime: __import__("sqlalchemy").DateTime(timezone=True),
    }
