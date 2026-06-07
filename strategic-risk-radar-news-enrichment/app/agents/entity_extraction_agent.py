from ..models import EnrichmentState, empty_entities
from .base import BaseAgent


class EntityExtractionAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        text = self.article_text(state)
        entities = empty_entities()
        llm_entities = self.ollama.json_task(
            "Extract named entities from the news article as strict JSON only. "
            "Keys: countries,cities,airports,ports,airlines,companies,organizations,persons,military_groups,government_agencies. "
            "Values are arrays of strings. Do not infer entities that are not mentioned.",
            text[:6000],
        )
        for key in entities:
            for value in llm_entities.get(key, []) if isinstance(llm_entities.get(key), list) else []:
                self.add_entity(entities, key, str(value), confidence=0.7)
        return {**state, "entities": self.deduplicate_entities(entities)}
