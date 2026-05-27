"""Idempotent Qdrant collection bootstrap."""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    Distance,
    HnswConfigDiff,
    PayloadSchemaType,
    VectorParams,
)

from mnemo_api.config import Settings
from mnemo_api.logging import get_logger

log = get_logger(__name__)


async def ensure_collection(client: AsyncQdrantClient, settings: Settings) -> None:
    name = settings.qdrant_collection
    try:
        await client.get_collection(name)
        log.info("qdrant.collection.present", collection=name)
        return
    except (UnexpectedResponse, ValueError):
        pass

    await client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=settings.embed_dim, distance=Distance.COSINE),
        hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
    )
    for field, schema in (
        ("user_id", PayloadSchemaType.KEYWORD),
        ("tags", PayloadSchemaType.KEYWORD),
        ("source_type", PayloadSchemaType.KEYWORD),
        ("created_at", PayloadSchemaType.INTEGER),
    ):
        await client.create_payload_index(name, field, field_schema=schema)
    log.info("qdrant.collection.created", collection=name, dim=settings.embed_dim)
