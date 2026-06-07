from ..models import EnrichmentState
from .base import BaseAgent


class LoadRawArticleAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
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
