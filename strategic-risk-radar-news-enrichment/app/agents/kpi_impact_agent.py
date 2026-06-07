from ..domain_config import business_context, kpi_catalog_text
from ..models import EnrichmentState, KpiImpact
from .base import BaseAgent


class KpiImpactAgent(BaseAgent):
    def __call__(self, state: EnrichmentState) -> EnrichmentState:
        text = self.article_text(state)
        impacts: list[KpiImpact] = []
        llm_result = self.topic_ollama.json_task(
            "You are an ICP strategic risk analyst. Identify KPI impacts based only on the article. "
            "Return strict JSON only with key kpi_impacts. Each item must contain kpi_name, risk_score 0-100, "
            "risk_level low|medium|high|critical, impact_summary, evidence, confidence_score. "
            f"Business context: {business_context()}. Preferred KPI catalog: {kpi_catalog_text()}. "
            "Use the catalog when it fits; create another KPI name only when the article clearly needs it. "
            "Return an empty array if no KPI is affected.",
            text[:6000],
        )
        for item in llm_result.get("kpi_impacts", []) if isinstance(llm_result.get("kpi_impacts"), list) else []:
            kpi_name = self.clean_label(str(item.get("kpi_name", "")))
            if not kpi_name:
                continue
            score = self.clamp_score(item.get("risk_score", 0))
            impacts.append(
                KpiImpact(
                    kpi_name=kpi_name,
                    risk_score=score,
                    risk_level=self.normalize_level(str(item.get("risk_level", ""))),
                    impact_summary=str(item.get("impact_summary", ""))[:700],
                    evidence=str(item.get("evidence", ""))[:500],
                    confidence_score=self.clamp_confidence(item.get("confidence_score", 0.65)),
                )
            )
        return {**state, "kpi_impacts": self.deduplicate_kpi_impacts(impacts)}
