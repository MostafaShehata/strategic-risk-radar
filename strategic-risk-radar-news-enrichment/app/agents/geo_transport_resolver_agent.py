from ..models import EnrichmentState, empty_entities
from .base import BaseAgent
from .context import AIRPORTS, COUNTRIES, PORTS


class GeoTransportResolverAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
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
