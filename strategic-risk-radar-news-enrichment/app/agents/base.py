import re

from langdetect import LangDetectException, detect

from ..clients import FirecrawlerClient, OllamaClient, RagApiClient
from ..config import settings
from ..models import Entity, EnrichmentState, KpiImpact, PathImpact, TopicDecision, empty_entities
from ..repository import EnrichmentRepository
from .context import AIRPORTS, COUNTRIES, ICP_KPIS, PORTS


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

    def rule_kpi_impacts(self, text: str, state: EnrichmentState) -> list[KpiImpact]:
        impacts: list[KpiImpact] = []

        def add(kpi: str, score: int, summary: str, evidence: str) -> None:
            impacts.append(KpiImpact(kpi, score, self.risk_level(score), summary, evidence, 0.7))

        if any(self.has_term(text, term) for term in ("airport", "airspace", "flight", "airline", "passenger")):
            add("Airport Operations", 55, "Potential effect on flight schedules, airspace availability, or airport operations.", "Aviation terms detected in article.")
            add("Passenger Flow", 50, "Potential passenger flow disruption or travel demand change.", "Passenger or flight terms detected.")
        if any(self.has_term(text, term) for term in ("port", "shipping", "vessel", "cargo", "hormuz", "suez")):
            add("Port Operations", 65, "Potential effect on port throughput, vessel movement, or maritime operations.", "Maritime or port terms detected.")
            add("Cargo Clearance", 60, "Potential cargo inspection, clearance, or routing pressure.", "Cargo or customs-adjacent terms detected.")
            add("Maritime Route Continuity", 70 if "hormuz" in text or "suez" in text else 55, "Potential disruption to strategic sea routes affecting UAE trade routes.", "Chokepoint or maritime routing terms detected.")
        if any(self.has_term(text, term) for term in ("border", "passport", "trafficking", "smuggling", "fraud")):
            add("Border Security", 65, "Potential increase in border screening or interdiction pressure.", "Border security terms detected.")
            add("Identity and Document Fraud", 55, "Potential identity, passport, or document-fraud exposure.", "Identity or document-risk terms detected.")
        if any(self.has_term(text, term) for term in ("visa", "residency", "overstay")):
            add("Visa and Residency Compliance", 55, "Potential compliance pressure from visa, residency, or overstay signals.", "Visa or residency terms detected.")
        if any(self.has_term(text, term) for term in ("migration", "refugee", "displacement", "evacuation")):
            add("Migration Pressure", 65, "Potential inbound or transit migration pressure affecting UAE readiness.", "Migration or displacement terms detected.")
        if any(self.has_term(text, term) for term in ("war", "attack", "missile", "sanctions", "closure", "blocked", "disruption")):
            add("Government Service Continuity", 50, "Potential need for cross-agency monitoring and service continuity planning.", "Escalation or disruption terms detected.")
        if state.get("path_impacts"):
            add("Government Service Continuity", 65, "Route impact detected; decision makers may need coordinated monitoring.", "Path Impact Agent created route risk.")
        return impacts or [KpiImpact("Government Service Continuity", 20, "low", "Article retained for monitoring but no direct ICP KPI impact was detected.", "No direct operational KPI terms detected.", 0.55)]

    def deduplicate_kpi_impacts(self, impacts: list[KpiImpact]) -> list[KpiImpact]:
        best: dict[str, KpiImpact] = {}
        for impact in impacts:
            current = best.get(impact.kpi_name)
            if not current or impact.risk_score > current.risk_score:
                impact.risk_score = self.clamp_score(impact.risk_score)
                impact.risk_level = self.risk_level(impact.risk_score)
                best[impact.kpi_name] = impact
        return sorted(best.values(), key=lambda item: item.risk_score, reverse=True)

    def fallback_topic_proposal(self, state: EnrichmentState) -> TopicDecision:
        text = self.article_text(state).casefold()
        countries = [entity.normalized_name or entity.name for entity in state.get("entities", {}).get("countries", [])]
        kpis = [impact.kpi_name for impact in state.get("kpi_impacts", [])[:5]]
        if "hormuz" in text:
            title, key, event = "Strait of Hormuz Blocking Risk", "strait_of_hormuz_blocking_risk", "maritime_chokepoint_disruption"
        elif "suez" in text:
            title, key, event = "Suez Canal Shipping Disruption", "suez_canal_shipping_disruption", "maritime_chokepoint_disruption"
        elif "iran" in text and any(term in text for term in ("war", "missile", "attack", "ceasefire", "escalation")):
            title, key, event = "Iran War Escalation", "iran_war_escalation", "regional_conflict"
        elif "airspace" in text or "flight" in text or "airport" in text:
            title, key, event = "Regional Airspace and Airport Disruption", "regional_airspace_airport_disruption", "aviation_disruption"
        elif any(term in text for term in ("migration", "refugee", "displacement")):
            title, key, event = "Conflict Driven Migration Pressure", "conflict_driven_migration_pressure", "migration_pressure"
        elif any(term in text for term in ("visa", "residency", "overstay")):
            title, key, event = "Visa and Residency Compliance Pressure", "visa_residency_compliance_pressure", "visa_residency_pressure"
        elif countries:
            title = f"{countries[0]} Strategic Monitoring"
            key = self.normalize_topic_key(title)
            event = "strategic_monitoring"
        else:
            title, key, event = "General Strategic Monitoring", "general_strategic_monitoring", "strategic_monitoring"
        return TopicDecision(
            action="create",
            topic_key=key,
            title=title,
            summary=state.get("summary", "")[:700],
            event_type=event,
            uae_impact=self.default_uae_impact(state, kpis),
            affected_kpis=kpis or ["Government Service Continuity"],
            llm_match_confidence=0.55,
        )

    def default_uae_impact(self, state: EnrichmentState, kpis: list[str]) -> str:
        if kpis:
            return "Potential UAE impact across " + ", ".join(kpis[:4]) + ". Monitor related news for escalation and operational changes."
        return "No direct UAE operational impact was detected yet; keep for strategic monitoring."

    def normalize_topic_key(self, value: str) -> str:
        key = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
        return key[:120] or "general_strategic_monitoring"

    def normalize_kpi_name(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip().casefold()
        for kpi in ICP_KPIS:
            if normalized == kpi.casefold():
                return kpi
        return ""

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

    def normalize_level(self, level: str, score: int) -> str:
        level = level.casefold().strip()
        return level if level in {"low", "medium", "high", "critical"} else self.risk_level(score)

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

    def should_use_topic_llm(self, state: EnrichmentState) -> bool:
        if not settings.enable_topic_llm:
            return False
        text = self.article_text(state).casefold()
        if state.get("path_impacts"):
            return True
        risk_terms = (
            "war",
            "attack",
            "missile",
            "sanctions",
            "ceasefire",
            "escalation",
            "closure",
            "closed",
            "blocked",
            "disruption",
            "delay",
            "evacuation",
            "trafficking",
            "smuggling",
            "fraud",
            "overstay",
        )
        return self.has_strategic_anchor(text) and any(self.has_term(text, term) for term in risk_terms)

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
