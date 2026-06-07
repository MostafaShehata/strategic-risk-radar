from typing import Any

from pydantic import BaseModel, Field


class IngestTextRequest(BaseModel):
    source: str = Field(min_length=1)
    text: str = Field(min_length=1)
    document_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    filters: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    source: str
    document_type: str
    chunks_indexed: int
    collection: str


class SearchHit(BaseModel):
    source: str
    document_type: str
    chunk_index: int
    score: float
    text: str
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
