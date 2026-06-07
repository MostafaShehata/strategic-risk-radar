from ..clients import FirecrawlerClient, OllamaClient, RagApiClient
from ..models import EnrichmentState
from ..repository import EnrichmentRepository
from .entity_extraction_agent import EntityExtractionAgent
from .final_validator_agent import FinalValidatorAgent
from .geo_transport_resolver_agent import GeoTransportResolverAgent
from .kpi_impact_agent import KpiImpactAgent
from .load_raw_article_agent import LoadRawArticleAgent
from .normalize_agent import NormalizeAgent
from .path_impact_agent import PathImpactAgent
from .rag_index_agent import RagIndexAgent
from .risk_scoring_agent import RiskScoringAgent
from .save_enriched_article_agent import SaveEnrichedArticleAgent
from .topic_clustering_agent import TopicClusteringAgent


class EnrichmentWorkflowAgents:
    def __init__(
        self,
        repository: EnrichmentRepository,
        firecrawler: FirecrawlerClient,
        ollama: OllamaClient,
        topic_ollama: OllamaClient,
        rag: RagApiClient,
    ) -> None:
        kwargs = {
            "repository": repository,
            "firecrawler": firecrawler,
            "ollama": ollama,
            "topic_ollama": topic_ollama,
            "rag": rag,
        }
        self.load_raw_article_agent = LoadRawArticleAgent(**kwargs)
        self.normalize_agent = NormalizeAgent(**kwargs)
        self.entity_extraction_agent = EntityExtractionAgent(**kwargs)
        self.geo_transport_resolver_agent = GeoTransportResolverAgent(**kwargs)
        self.path_impact_agent = PathImpactAgent(**kwargs)
        self.kpi_impact_agent = KpiImpactAgent(**kwargs)
        self.risk_scoring_agent = RiskScoringAgent(**kwargs)
        self.topic_clustering_agent = TopicClusteringAgent(**kwargs)
        self.final_validator_agent = FinalValidatorAgent(**kwargs)
        self.save_enriched_article_agent = SaveEnrichedArticleAgent(**kwargs)
        self.rag_index_agent = RagIndexAgent(**kwargs)

    def load_raw_article(self, state: EnrichmentState) -> EnrichmentState:
        return self.load_raw_article_agent(state)

    def normalize(self, state: EnrichmentState) -> EnrichmentState:
        return self.normalize_agent(state)

    def entity_extraction(self, state: EnrichmentState) -> EnrichmentState:
        return self.entity_extraction_agent(state)

    def resolve_geo_transport(self, state: EnrichmentState) -> EnrichmentState:
        return self.geo_transport_resolver_agent(state)

    def path_impact(self, state: EnrichmentState) -> EnrichmentState:
        return self.path_impact_agent(state)

    def kpi_impact(self, state: EnrichmentState) -> EnrichmentState:
        return self.kpi_impact_agent(state)

    def risk_scoring(self, state: EnrichmentState) -> EnrichmentState:
        return self.risk_scoring_agent(state)

    def topic_clustering(self, state: EnrichmentState) -> EnrichmentState:
        return self.topic_clustering_agent(state)

    def final_validator(self, state: EnrichmentState) -> EnrichmentState:
        return self.final_validator_agent(state)

    def save_enriched_article(self, state: EnrichmentState) -> EnrichmentState:
        return self.save_enriched_article_agent(state)

    def rag_index(self, state: EnrichmentState) -> EnrichmentState:
        return self.rag_index_agent(state)
