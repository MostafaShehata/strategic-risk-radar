from ..config import settings
from ..models import EnrichmentState
from .base import BaseAgent


class SaveEnrichedArticleAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        enriched_id = self.repository.save_enrichment(state, settings.model_name)
        trace = dict(state.get("trace", {}))
        trace["enriched_news_item_id"] = str(enriched_id)
        return {**state, "trace": trace}
