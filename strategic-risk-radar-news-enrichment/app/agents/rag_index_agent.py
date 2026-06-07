from ..models import EnrichmentState
from .base import BaseAgent


class RagIndexAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
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
