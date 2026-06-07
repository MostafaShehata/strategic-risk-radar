from ..models import EnrichmentState
from .base import BaseAgent


class FinalValidatorAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        errors = []
        if not state.get("title"):
            errors.append("missing title")
        if not state.get("normalized_body") and not state.get("summary"):
            errors.append("missing body and summary")
        if not isinstance(state.get("risk_score"), int):
            errors.append("risk score is not integer")
        if state.get("risk_level") not in {"low", "medium", "high", "critical"}:
            errors.append("missing model risk level")
        topic = state.get("topic")
        if not topic or not (topic.topic_key or topic.title):
            errors.append("missing model topic")
        if not state.get("risk_reason"):
            errors.append("missing model risk reason")
        status = "needs_review" if errors else "enriched"
        return {**state, "validation_errors": errors, "enrichment_status": status}
