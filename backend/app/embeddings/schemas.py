"""Pydantic schemas for embedding/indexing endpoints."""

from uuid import UUID

from pydantic import BaseModel


class EmbeddingTaskRead(BaseModel):
    document_id: UUID
    celery_task_id: str
    action: str


class StaleEmbeddingRead(BaseModel):
    document_ids: list[UUID]
    count: int
