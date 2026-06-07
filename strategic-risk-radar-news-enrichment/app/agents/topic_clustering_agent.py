from ..config import settings
from ..models import EnrichmentState, TopicDecision
from .base import BaseAgent


class TopicClusteringAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        proposal = self.strategic_topic_proposal(state)
        if not proposal.topic_key and not proposal.title:
            return {**state, "topic": proposal}
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
        llm_result = self.topic_ollama.json_task(
            "You are an ICP strategic intelligence analyst. Create or classify the strategic situation topic, not the article headline. "
            "Return strict JSON only with keys: topic_title, topic_key, event_type, summary, uae_impact, affected_kpis array, confidence_score. "
            "The topic must be a strategic situation useful for UAE decision makers. Do not use the article title as the topic unless it is already a strategic event. "
            "topic_key must be lowercase words separated by underscores and stable across similar articles. "
            "Return empty strings and an empty affected_kpis array only if no strategic topic can be supported by the article.",
            self.article_text(state)[:6000],
        )
        title = self.clean_label(str(llm_result.get("topic_title") or ""))
        topic_key = self.normalize_topic_key(str(llm_result.get("topic_key") or title))
        affected_kpis = llm_result.get("affected_kpis") if isinstance(llm_result.get("affected_kpis"), list) else []
        return TopicDecision(
            action="create",
            topic_key=topic_key,
            title=title,
            summary=str(llm_result.get("summary") or "").strip()[:1000],
            event_type=self.clean_label(str(llm_result.get("event_type") or "")),
            uae_impact=str(llm_result.get("uae_impact") or "").strip()[:1200],
            affected_kpis=[self.clean_label(str(kpi)) for kpi in affected_kpis if str(kpi).strip()][:8],
            llm_match_confidence=self.clamp_confidence(llm_result.get("confidence_score", 0)),
        )
