from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RawItem:
    source_id: str
    source_type: str
    external_id: str
    url: str
    title: str
    summary: str
    published_at: datetime | None
    keyword: str
    raw_payload: dict[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class KeywordResult:
    keyword: str
    request_count: int
    retrieved_count: int
    items: tuple[RawItem, ...]

