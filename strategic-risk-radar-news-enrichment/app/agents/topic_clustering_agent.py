from ..config import settings
from ..models import EnrichmentState, TopicDecision
from .base import BaseAgent


class TopicClusteringAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
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

    def strategic_topic_proposal(self, state: EnrichmentState) -> TopicDecision:
        fallback = self.fallback_topic_proposal(state)
        llm_result = {}
        if self.should_use_topic_llm(state):
            llm_result = self.topic_ollama.json_task(
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
