import re

from langdetect import LangDetectException, detect

from ..clients import FirecrawlerClient, OllamaClient, RagApiClient
from ..models import Entity, EnrichmentState, KpiImpact, PathImpact, empty_entities
from ..repository import EnrichmentRepository


class BaseAgent:
    def __init__(
        self,
        repository: EnrichmentRepository,
        firecrawler: FirecrawlerClient,
        ollama: OllamaClient,
        topic_ollama: OllamaClient,
        rag: RagApiClient,
    ) -> None:
        self.repository = repository
        self.firecrawler = firecrawler
        self.ollama = ollama
        self.topic_ollama = topic_ollama
        self.rag = rag

    def article_text(self, state: EnrichmentState) -> str:
        return "\n\n".join([state.get("title", ""), state.get("summary", ""), state.get("normalized_body", "")])

    def clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def detect_language(self, text: str) -> str:
        try:
            return detect(text) if text.strip() else "unknown"
        except LangDetectException:
            return "unknown"

    def add_entity(
        self,
        entities: dict[str, list[Entity]],
        key: str,
        name: str,
        normalized_name: str = "",
        code: str = "",
        country_code: str = "",
        confidence: float = 0.6,
    ) -> None:
        if key in entities and name.strip():
            entities[key].append(Entity(key, name.strip(), normalized_name, code, country_code, confidence))

    def deduplicate_entities(self, entities: dict[str, list[Entity]]) -> dict[str, list[Entity]]:
        result = empty_entities()
        for key, values in entities.items():
            seen = set()
            for entity in values:
                marker = (entity.normalized_name or entity.name).casefold()
                if marker in seen:
                    continue
                seen.add(marker)
                result[key].append(entity)
        return result

    def deduplicate_impacts(self, impacts: list[PathImpact]) -> list[PathImpact]:
        seen = set()
        result = []
        for impact in impacts:
            if impact.path_code in seen:
                continue
            seen.add(impact.path_code)
            result.append(impact)
        return result

    def deduplicate_kpi_impacts(self, impacts: list[KpiImpact]) -> list[KpiImpact]:
        best: dict[str, KpiImpact] = {}
        for impact in impacts:
            current = best.get(impact.kpi_name)
            if not current or impact.risk_score > current.risk_score:
                impact.risk_score = self.clamp_score(impact.risk_score)
                impact.risk_level = self.normalize_level(impact.risk_level)
                best[impact.kpi_name] = impact
        return sorted(best.values(), key=lambda item: item.risk_score, reverse=True)

    def normalize_topic_key(self, value: str) -> str:
        key = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
        return key[:120]

    def clean_label(self, value: str, max_length: int = 120) -> str:
        return re.sub(r"\s+", " ", value).strip()[:max_length]

    def clamp_score(self, value) -> int:
        try:
            return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return 0

    def clamp_confidence(self, value) -> float:
        try:
            return max(0, min(1, float(value)))
        except (TypeError, ValueError):
            return 0.6

    def normalize_level(self, level: str) -> str:
        level = level.casefold().strip()
        return level if level in {"low", "medium", "high", "critical"} else "unknown"
