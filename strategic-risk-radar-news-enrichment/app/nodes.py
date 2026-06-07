import re
from datetime import datetime

from langdetect import LangDetectException, detect

from .clients import FirecrawlerClient, OllamaClient, RagApiClient
from .config import settings
from .models import Entity, EnrichmentState, KpiImpact, PathImpact, TopicDecision, empty_entities
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

ICP_KPIS = (
    "Airport Operations",
    "Passenger Flow",
    "Port Operations",
    "Cargo Clearance",
    "Maritime Route Continuity",
    "Border Security",
    "Visa and Residency Compliance",
    "Identity and Document Fraud",
    "Migration Pressure",
    "Government Service Continuity",
)


class EnrichmentNodes:
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

    def kpi_impact(self, state: EnrichmentState) -> EnrichmentState:
        text = self.article_text(state)
        impacts = self.rule_kpi_impacts(text.casefold(), state)
        llm_result = self.topic_ollama.json_task(
            "You are an ICP strategic risk analyst. Return strict JSON only with key kpi_impacts. "
            "Each item must contain kpi_name, risk_score 0-100, risk_level low|medium|high|critical, "
            "impact_summary, evidence, confidence_score. Use only these KPI names: "
            + ", ".join(ICP_KPIS),
            text[:6000],
        )
        for item in llm_result.get("kpi_impacts", []) if isinstance(llm_result.get("kpi_impacts"), list) else []:
            kpi_name = self.normalize_kpi_name(str(item.get("kpi_name", "")))
            if not kpi_name:
                continue
            impacts.append(
                KpiImpact(
                    kpi_name=kpi_name,
                    risk_score=self.clamp_score(item.get("risk_score", 0)),
                    risk_level=self.normalize_level(str(item.get("risk_level", "")), self.clamp_score(item.get("risk_score", 0))),
                    impact_summary=str(item.get("impact_summary", ""))[:700],
                    evidence=str(item.get("evidence", ""))[:500],
                    confidence_score=self.clamp_confidence(item.get("confidence_score", 0.65)),
                )
            )
        impacts = self.deduplicate_kpi_impacts(impacts)
        return {**state, "kpi_impacts": impacts}

    def risk_scoring(self, state: EnrichmentState) -> EnrichmentState:
        text = self.article_text(state).casefold()
        score = max([value for term, value in RISK_TERMS.items() if self.has_term(text, term)] or [20])
        domains = self.detect_domains(text)
        if state.get("path_impacts"):
            score = max(score, 60)
        if state.get("kpi_impacts"):
            score = max(score, max(impact.risk_score for impact in state["kpi_impacts"]))
        if not state.get("path_impacts") and not self.has_strategic_anchor(text):
            score = min(score, 35)
        if domains == ["strategic_monitoring"] and not state.get("path_impacts"):
            score = min(score, 25)
        llm_result = self.topic_ollama.json_task(
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
        proposal = self.strategic_topic_proposal(state)
        existing = self.repository.find_topic_by_key(proposal.topic_key)
        if existing and existing[1] >= settings.topic_match_threshold:
            proposal.topic_id = existing[0]
            proposal.action = "attach"
            proposal.similarity_score = existing[1]
            proposal.llm_match_confidence = max(proposal.llm_match_confidence, 0.9)
        else:
            proposal.action = "create"
        return {**state, "topic": proposal}

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

    def strategic_topic_proposal(self, state: EnrichmentState) -> TopicDecision:
        fallback = self.fallback_topic_proposal(state)
        llm_result = self.ollama.json_task(
            "You are an ICP strategic intelligence analyst. Create or classify the strategic situation topic, not the article headline. "
            "Return strict JSON only with keys: topic_title, topic_key, event_type, summary, uae_impact, affected_kpis array, confidence_score. "
            "Good topic examples: Iran War Escalation, Strait of Hormuz Blocking Risk, Regional Airspace Closure, Russia Ukraine Migration Pressure. "
            "topic_key must be lowercase words separated by underscores and stable across similar articles.",
            self.article_text(state)[:6000],
        )
        title = str(llm_result.get("topic_title") or fallback.title).strip()
        topic_key = self.normalize_topic_key(str(llm_result.get("topic_key") or title or fallback.topic_key))
        affected_kpis = llm_result.get("affected_kpis") if isinstance(llm_result.get("affected_kpis"), list) else fallback.affected_kpis
        return TopicDecision(
            action="create",
            topic_key=topic_key or fallback.topic_key,
            title=title or fallback.title,
            summary=str(llm_result.get("summary") or fallback.summary).strip()[:1000],
            event_type=str(llm_result.get("event_type") or fallback.event_type).strip()[:120],
            uae_impact=str(llm_result.get("uae_impact") or fallback.uae_impact).strip()[:1200],
            affected_kpis=[self.normalize_kpi_name(str(kpi)) or str(kpi) for kpi in affected_kpis][:8],
            llm_match_confidence=self.clamp_confidence(llm_result.get("confidence_score", fallback.llm_match_confidence)),
        )

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
