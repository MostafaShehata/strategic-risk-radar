from ..models import EnrichmentState, PathImpact
from .base import BaseAgent
from .context import TRANSPORT_TERMS


class PathImpactAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        countries = [entity.code or entity.country_code for entity in state.get("entities", {}).get("countries", [])]
        text = self.article_text(state).casefold()
        impacts: list[PathImpact] = []
        has_transport_context = any(self.has_term(text, term) for term in TRANSPORT_TERMS)
        if has_transport_context and ("ARE" in countries or "uae" in text or "dubai" in text):
            for origin in [code for code in countries if code and code != "ARE"]:
                impacts.append(self.create_path_impact(origin, "ARE", text))
        if not impacts and any(self.has_term(text, term) for term in ("hormuz", "suez", "shipping", "cargo", "port")):
            impacts.append(self.create_path_impact("GLOBAL", "ARE", text))
        llm_result = self.ollama.json_task(
            "Create path impacts as strict JSON only: {\"path_impacts\":[{\"origin\":\"IRN\",\"destination\":\"ARE\",\"impact_type\":\"CARGO_DELAY\",\"impact_level\":\"HIGH_RISK\",\"reason\":\"...\"}]}",
            self.article_text(state)[:5000],
        )
        for item in llm_result.get("path_impacts", []) if isinstance(llm_result.get("path_impacts"), list) else []:
            origin = str(item.get("origin", "")).upper()
            destination = str(item.get("destination", "")).upper()
            level = str(item.get("impact_level", "WATCH")).upper()
            impact_type = str(item.get("impact_type", "WATCH")).upper()
            if origin and destination:
                impacts.append(PathImpact(origin, destination, f"{origin}-{destination}-{level}", impact_type, level, str(item.get("reason", "")), 0.7))
        return {**state, "path_impacts": self.deduplicate_impacts(impacts)}
