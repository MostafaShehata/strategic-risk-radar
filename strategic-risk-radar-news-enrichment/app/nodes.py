import re
from datetime import datetime

from langdetect import LangDetectException, detect

from .clients import FirecrawlerClient, OllamaClient, RagApiClient
from .config import settings
from .models import Entity, EnrichmentState, PathImpact, TopicDecision, empty_entities
from .repository import EnrichmentRepository


COUNTRIES = {
    "united arab emirates": ("United Arab Emirates", "ARE"),
    "uae": ("United Arab Emirates", "ARE"),
    "iran": ("Iran", "IRN"),
    "egypt": ("Egypt", "EGY"),
    "russia": ("Russia", "RUS"),
    "ukraine": ("Ukraine", "UKR"),
    "china": ("China", "CHN"),
    "india": ("India", "IND"),
    "saudi arabia": ("Saudi Arabia", "SAU"),
    "qatar": ("Qatar", "QAT"),
    "oman": ("Oman", "OMN"),
    "iraq": ("Iraq", "IRQ"),
    "israel": ("Israel", "ISR"),
    "yemen": ("Yemen", "YEM"),
}

AIRPORTS = {
    "dubai international airport": ("Dubai International Airport", "DXB", "ARE"),
    "dxb": ("Dubai International Airport", "DXB", "ARE"),
    "abu dhabi international airport": ("Zayed International Airport", "AUH", "ARE"),
    "zayed international airport": ("Zayed International Airport", "AUH", "ARE"),
    "cairo international airport": ("Cairo International Airport", "CAI", "EGY"),
}

PORTS = {
    "jebel ali": ("Jebel Ali Port", "AEJEA", "ARE"),
    "port rashid": ("Port Rashid", "AEPRA", "ARE"),
    "fujairah": ("Port of Fujairah", "AEFJR", "ARE"),
    "suez canal": ("Suez Canal", "EGSUZ", "EGY"),
    "strait of hormuz": ("Strait of Hormuz", "IRHOM", "IRN"),
}

RISK_TERMS = {
    "blocked": 90,
    "closure": 80,
    "closed": 80,
    "attack": 75,
    "war": 75,
    "missile": 75,
    "sanctions": 65,
    "disruption": 60,
    "delay": 45,
    "fraud": 55,
    "trafficking": 70,
    "visa": 40,
    "refugee": 55,
}

TRANSPORT_TERMS = (
    "cargo",
    "shipping",
    "port",
    "vessel",
    "airport",
    "airspace",
    "flight",
    "airline",
    "customs",
    "border",
    "visa",
    "passport",
    "migration",
    "refugee",
    "trafficking",
    "smuggling",
)


class EnrichmentNodes:
    def __init__(
        self,
        repository: EnrichmentRepository,
        firecrawler: FirecrawlerClient,
        ollama: OllamaClient,
        rag: RagApiClient,
    ) -> None:
        self.repository = repository
        self.firecrawler = firecrawler
        self.ollama = ollama
        self.rag = rag

    def load_raw_article(self, state: EnrichmentState) -> EnrichmentState:
        raw = state["raw"]
        return {
            **state,
            "title": raw.title,
            "summary": raw.summary,
            "publication_date": raw.published_at,
            "source_id": raw.source_id,
            "source_type": raw.source_type,
            "trace": {"raw_item_id": str(raw.id)},
        }

    def normalize(self, state: EnrichmentState) -> EnrichmentState:
        raw = state["raw"]
        body = raw.body.strip()
        body_source = "source_api" if body else "none"
        fetch_status = "not_needed" if len(body) >= settings.crawler_min_body_chars else "not_attempted"
        fetch_error = None
        if len(body) < settings.crawler_min_body_chars and raw.url:
            result = self.firecrawler.crawl(raw.url, raw.source_id, str(raw.id))
            self.repository.save_content_fetch(raw.id, raw.url, result)
            fetch_status = result.get("status", "failed")
            fetch_error = result.get("error_message")
            if result.get("body"):
                body = result["body"]
                body_source = "crawler"
            if result.get("title") and len(result["title"]) > len(state.get("title", "")):
                state["title"] = result["title"]
        language = self.detect_language(" ".join([state.get("title", ""), state.get("summary", ""), body]))
        return {
            **state,
            "language": language,
            "normalized_body": self.clean_text(body),
            "body_source": body_source,
            "content_fetch_status": fetch_status,
            "content_fetch_error": fetch_error,
        }

    def entity_extraction(self, state: EnrichmentState) -> EnrichmentState:
        text = self.article_text(state)
        entities = empty_entities()
        self.add_rule_entities(text, entities)
        llm_entities = self.ollama.json_task(
            "Extract entities from news as strict JSON only. Keys: countries,cities,airports,ports,airlines,companies,organizations,persons,military_groups,government_agencies. Values are arrays of strings.",
            text[:6000],
        )
        for key in entities:
            for value in llm_entities.get(key, []) if isinstance(llm_entities.get(key), list) else []:
                self.add_entity(entities, key, str(value), confidence=0.7)
        return {**state, "entities": self.deduplicate_entities(entities)}

    def resolve_geo_transport(self, state: EnrichmentState) -> EnrichmentState:
        entities = state.get("entities", empty_entities())
        for entity in entities.get("countries", []):
            key = entity.name.casefold()
            if key in COUNTRIES:
                entity.normalized_name, entity.code = COUNTRIES[key]
                entity.country_code = entity.code
        for entity in entities.get("airports", []):
            key = entity.name.casefold()
            if key in AIRPORTS:
                entity.normalized_name, entity.code, entity.country_code = AIRPORTS[key]
        for entity in entities.get("ports", []):
            key = entity.name.casefold()
            if key in PORTS:
                entity.normalized_name, entity.code, entity.country_code = PORTS[key]
        return {**state, "entities": entities}

    def path_impact(self, state: EnrichmentState) -> EnrichmentState:
        countries = [entity.code or entity.country_code for entity in state.get("entities", {}).get("countries", [])]
        text = self.article_text(state).casefold()
        impacts: list[PathImpact] = []
        has_transport_context = any(self.has_term(text, term) for term in TRANSPORT_TERMS)
        if has_transport_context and ("ARE" in countries or "uae" in text or "dubai" in text):
            for origin in [code for code in countries if code and code != "ARE"]:
                impacts.append(self.create_path_impact(origin, "ARE", text))
        if not impacts and any(self.has_term(text, term) for term in ("hormuz", "suez", "shipping", "cargo", "port")):
            impacts.append(self.create_path_impact("GLOBAL", "ARE", text))
        llm_result = self.ollama.json_task(
            "Create path impacts as strict JSON only: {\"path_impacts\":[{\"origin\":\"IRN\",\"destination\":\"ARE\",\"impact_type\":\"CARGO_DELAY\",\"impact_level\":\"HIGH_RISK\",\"reason\":\"...\"}]}",
            self.article_text(state)[:5000],
        )
        for item in llm_result.get("path_impacts", []) if isinstance(llm_result.get("path_impacts"), list) else []:
            origin = str(item.get("origin", "")).upper()
            destination = str(item.get("destination", "")).upper()
            level = str(item.get("impact_level", "WATCH")).upper()
            impact_type = str(item.get("impact_type", "WATCH")).upper()
            if origin and destination:
                impacts.append(PathImpact(origin, destination, f"{origin}-{destination}-{level}", impact_type, level, str(item.get("reason", "")), 0.7))
        return {**state, "path_impacts": self.deduplicate_impacts(impacts)}

    def risk_scoring(self, state: EnrichmentState) -> EnrichmentState:
        text = self.article_text(state).casefold()
        score = max([value for term, value in RISK_TERMS.items() if self.has_term(text, term)] or [20])
        domains = self.detect_domains(text)
        if state.get("path_impacts"):
            score = max(score, 60)
        if not state.get("path_impacts") and not self.has_strategic_anchor(text):
            score = min(score, 35)
        if domains == ["strategic_monitoring"] and not state.get("path_impacts"):
            score = min(score, 25)
        llm_result = self.ollama.json_task(
            "Score strategic risk as strict JSON only: {\"risk_score\":0-100,\"risk_level\":\"low|medium|high|critical\",\"risk_domains\":[\"cargo\"],\"risk_reason\":\"...\",\"confidence_score\":0.0}",
            self.article_text(state)[:5000],
        )
        score = int(llm_result.get("risk_score", score) or score)
        score = max(0, min(100, score))
        risk_level = str(llm_result.get("risk_level") or self.risk_level(score)).lower()
        risk_domains = llm_result.get("risk_domains") if isinstance(llm_result.get("risk_domains"), list) else domains
        reason = str(llm_result.get("risk_reason") or self.default_risk_reason(state, score))
        confidence = float(llm_result.get("confidence_score", 0.65) or 0.65)
        return {
            **state,
            "risk_score": score,
            "risk_level": risk_level if risk_level in {"low", "medium", "high", "critical"} else self.risk_level(score),
            "risk_domains": risk_domains,
            "risk_reason": reason,
            "confidence_score": max(0, min(1, confidence)),
        }

    def topic_clustering(self, state: EnrichmentState) -> EnrichmentState:
        signature = self.repository.topic_signature(state)
        existing = self.repository.find_topic_by_signature(signature)
        if existing and existing[1] >= settings.topic_match_threshold:
            decision = TopicDecision(topic_id=existing[0], action="attach", similarity_score=existing[1], llm_match_confidence=0.9)
        else:
            decision = TopicDecision(action="create", similarity_score=0, llm_match_confidence=0)
        return {**state, "topic": decision}

    def final_validator(self, state: EnrichmentState) -> EnrichmentState:
        errors = []
        if not state.get("title"):
            errors.append("missing title")
        if not state.get("normalized_body") and not state.get("summary"):
            errors.append("missing body and summary")
        if not isinstance(state.get("risk_score"), int):
            errors.append("risk score is not integer")
        status = "needs_review" if errors else "enriched"
        return {**state, "validation_errors": errors, "enrichment_status": status}

    def save_enriched_article(self, state: EnrichmentState) -> EnrichmentState:
        enriched_id = self.repository.save_enrichment(state, settings.model_name)
        trace = dict(state.get("trace", {}))
        trace["enriched_news_item_id"] = str(enriched_id)
        return {**state, "trace": trace}

    def rag_index(self, state: EnrichmentState) -> EnrichmentState:
        raw = state["raw"]
        self.rag.index_article(
            source=f"raw-news:{raw.id}",
            text="\n\n".join([state.get("title", ""), state.get("summary", ""), state.get("normalized_body", "")]),
            metadata={
                "raw_news_item_id": str(raw.id),
                "source_id": raw.source_id,
                "risk_level": state.get("risk_level", ""),
                "risk_score": state.get("risk_score", 0),
                "domains": ",".join(state.get("risk_domains", [])),
            },
        )
        return state

    def article_text(self, state: EnrichmentState) -> str:
        return "\n\n".join([state.get("title", ""), state.get("summary", ""), state.get("normalized_body", "")])

    def clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def detect_language(self, text: str) -> str:
        try:
            return detect(text) if text.strip() else "unknown"
        except LangDetectException:
            return "unknown"

    def add_rule_entities(self, text: str, entities: dict[str, list[Entity]]) -> None:
        lower = text.casefold()
        for alias, (name, code) in COUNTRIES.items():
            if self.has_term(lower, alias):
                self.add_entity(entities, "countries", name, name, code, code, 0.9)
        for alias, (name, code, country) in AIRPORTS.items():
            if self.has_term(lower, alias):
                self.add_entity(entities, "airports", name, name, code, country, 0.9)
        for alias, (name, code, country) in PORTS.items():
            if self.has_term(lower, alias):
                self.add_entity(entities, "ports", name, name, code, country, 0.9)
        for airline in ("emirates", "etihad", "flydubai", "qatar airways", "egyptair"):
            if self.has_term(lower, airline):
                self.add_entity(entities, "airlines", airline.title(), confidence=0.8)

    def has_term(self, text: str, term: str) -> bool:
        return re.search(rf"(?<![a-z0-9]){re.escape(term.casefold())}(?![a-z0-9])", text) is not None

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

    def create_path_impact(self, origin: str, destination: str, text: str) -> PathImpact:
        level = "BLOCKED" if "blocked" in text or "closure" in text else "HIGH_RISK" if "attack" in text or "war" in text or "disruption" in text else "WATCH"
        impact_type = "CARGO_DELAY" if "cargo" in text or "shipping" in text or "port" in text else "PASSENGER_DISRUPTION"
        return PathImpact(origin, destination, f"{origin}-{destination}-{level}", impact_type, level, "Detected route-impact terms in article", 0.7)

    def deduplicate_impacts(self, impacts: list[PathImpact]) -> list[PathImpact]:
        seen = set()
        result = []
        for impact in impacts:
            if impact.path_code in seen:
                continue
            seen.add(impact.path_code)
            result.append(impact)
        return result

    def detect_domains(self, text: str) -> list[str]:
        domains = []
        if any(self.has_term(text, term) for term in ("cargo", "shipping", "port", "customs", "vessel")):
            domains.append("cargo")
        if any(self.has_term(text, term) for term in ("airport", "airspace", "flight", "airline", "passenger")):
            domains.append("passenger")
        if any(self.has_term(text, term) for term in ("visa", "residency", "overstay", "migration", "refugee")):
            domains.append("visa_residency")
        if any(self.has_term(text, term) for term in ("passport", "identity", "fraud", "trafficking", "smuggling")):
            domains.append("identity_border_security")
        return domains or ["strategic_monitoring"]

    def has_strategic_anchor(self, text: str) -> bool:
        anchor_terms = (
            "uae",
            "united arab emirates",
            "dubai",
            "abu dhabi",
            "hormuz",
            "suez",
            "cargo",
            "shipping",
            "customs",
            "border",
            "visa",
            "passport",
            "migration",
            "refugee",
            "trafficking",
            "smuggling",
            "airport",
            "airspace",
            "flight",
            "port",
        )
        return any(self.has_term(text, term) for term in anchor_terms)

    def risk_level(self, score: int) -> str:
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "medium"
        return "low"

    def default_risk_reason(self, state: EnrichmentState, score: int) -> str:
        return f"Risk score {score} based on article terms, entities, and path impact indicators."
