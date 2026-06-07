import json

from ..models import EnrichmentState, empty_entities
from .base import BaseAgent


class GeoTransportResolverAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        entities = state.get("entities", empty_entities())
        llm_result = self.ollama.json_task(
            "Resolve extracted geo and transport entities as strict JSON only. "
            "Return the same top-level keys: countries,cities,airports,ports,airlines,companies,organizations,persons,military_groups,government_agencies. "
            "Each value must be an array of objects with fields: name, normalized_name, code, country_code, confidence_score. "
            "Use ISO-3 country codes for countries, IATA/ICAO codes for airports when known, and UN/LOCODE or common maritime codes for ports when known. "
            "Do not add entities that were not present in the input. Leave unknown codes as empty strings.",
            self.entities_payload(entities),
        )
        for key, values in entities.items():
            resolved_items = llm_result.get(key, [])
            if not isinstance(resolved_items, list):
                continue
            by_name = {str(item.get("name", "")).casefold(): item for item in resolved_items if isinstance(item, dict)}
            for entity in values:
                item = by_name.get(entity.name.casefold())
                if not item:
                    continue
                entity.normalized_name = str(item.get("normalized_name") or entity.normalized_name)
                entity.code = str(item.get("code") or entity.code)
                entity.country_code = str(item.get("country_code") or entity.country_code)
                entity.confidence_score = self.clamp_confidence(item.get("confidence_score", entity.confidence_score))
        return {**state, "entities": entities}

    def entities_payload(self, entities) -> str:
        return json.dumps({key: [entity.name for entity in values] for key, values in entities.items()})
