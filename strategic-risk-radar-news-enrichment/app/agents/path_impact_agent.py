from ..models import EnrichmentState, PathImpact
from .base import BaseAgent


class PathImpactAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        impacts: list[PathImpact] = []
        llm_result = self.ollama.json_task(
            "You are an ICP strategic transport analyst. Create route/path impacts from the article as strict JSON only. "
            "Return {\"path_impacts\":[{\"origin\":\"IRN\",\"destination\":\"ARE\",\"impact_type\":\"CARGO_DELAY\","
            "\"impact_level\":\"HIGH_RISK\",\"reason\":\"...\",\"confidence_score\":0.0}]}. "
            "Use ISO-3 country codes where possible. Return an empty array when no route impact is supported by the article.",
            self.article_text(state)[:5000],
        )
        for item in llm_result.get("path_impacts", []) if isinstance(llm_result.get("path_impacts"), list) else []:
            origin = str(item.get("origin", "")).upper()
            destination = str(item.get("destination", "")).upper()
            level = str(item.get("impact_level", "WATCH")).upper()
            impact_type = str(item.get("impact_type", "WATCH")).upper()
            if origin and destination:
                impacts.append(
                    PathImpact(
                        origin,
                        destination,
                        f"{origin}-{destination}-{level}",
                        impact_type,
                        level,
                        str(item.get("reason", ""))[:700],
                        self.clamp_confidence(item.get("confidence_score", 0.6)),
                    )
                )
        return {**state, "path_impacts": self.deduplicate_impacts(impacts)}
