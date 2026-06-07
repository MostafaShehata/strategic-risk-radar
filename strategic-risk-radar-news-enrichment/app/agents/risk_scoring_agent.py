from ..domain_config import business_context, kpi_catalog_text
from ..models import EnrichmentState
from .base import BaseAgent


class RiskScoringAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        llm_result = self.topic_ollama.json_task(
            "You are an ICP strategic risk scoring agent. Score the article for UAE ICP decision makers. "
            "Return strict JSON only: {\"risk_score\":0-100,\"risk_level\":\"low|medium|high|critical\","
            "\"risk_domains\":[\"domain\"],\"risk_reason\":\"...\",\"confidence_score\":0.0}. "
            f"Business context: {business_context()}. KPI catalog: {kpi_catalog_text()}. "
            "Base the score only on the article, extracted entities, path impacts, and KPI impacts.",
            self.article_text(state)[:5000],
        )
        score = self.clamp_score(llm_result.get("risk_score", 0))
        risk_level = self.normalize_level(str(llm_result.get("risk_level") or ""))
        risk_domains = llm_result.get("risk_domains") if isinstance(llm_result.get("risk_domains"), list) else []
        reason = str(llm_result.get("risk_reason") or "")
        confidence = self.clamp_confidence(llm_result.get("confidence_score", 0))
        return {
            **state,
            "risk_score": score,
            "risk_level": risk_level,
            "risk_domains": risk_domains,
            "risk_reason": reason,
            "confidence_score": max(0, min(1, confidence)),
        }
