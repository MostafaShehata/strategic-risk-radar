from ..models import EnrichmentState
from .base import BaseAgent
from .context import RISK_TERMS


class RiskScoringAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
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
        llm_result = {}
        if self.should_use_topic_llm(state):
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
