from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID


@dataclass(frozen=True)
class RawArticle:
    id: UUID
    source_id: str
    source_type: str
    url: str
    title: str
    summary: str
    body: str
    published_at: datetime | None
    raw_payload: dict[str, Any]


@dataclass
class Entity:
    entity_type: str
    name: str
    normalized_name: str = ""
    code: str = ""
    country_code: str = ""
    confidence_score: float = 0.6


@dataclass
class PathImpact:
    origin: str
    destination: str
    path_code: str
    impact_type: str
    impact_level: str
    reason: str
    confidence_score: float = 0.6


@dataclass
class KpiImpact:
    kpi_name: str
    risk_score: int
    risk_level: str
    impact_summary: str
    evidence: str = ""
    confidence_score: float = 0.6


@dataclass
class TopicDecision:
    topic_id: str | None = None
    action: str = "create"
    similarity_score: float = 0.0
    llm_match_confidence: float = 0.0
    topic_key: str = ""
    title: str = ""
    summary: str = ""
    event_type: str = ""
    uae_impact: str = ""
    affected_kpis: list[str] = field(default_factory=list)


class EnrichmentState(TypedDict, total=False):
    raw: RawArticle
    title: str
    summary: str
    publication_date: datetime | None
    source_id: str
    source_type: str
    language: str
    normalized_body: str
    body_source: str
    content_fetch_status: str
    content_fetch_error: str | None
    entities: dict[str, list[Entity]]
    path_impacts: list[PathImpact]
    kpi_impacts: list[KpiImpact]
    risk_score: int
    risk_level: str
    risk_domains: list[str]
    risk_reason: str
    confidence_score: float
    topic: TopicDecision
    validation_errors: list[str]
    enrichment_status: str
    trace: dict[str, Any]


def empty_entities() -> dict[str, list[Entity]]:
    return {
        "countries": [],
        "cities": [],
        "airports": [],
        "ports": [],
        "airlines": [],
        "companies": [],
        "organizations": [],
        "persons": [],
        "military_groups": [],
        "government_agencies": [],
    }
