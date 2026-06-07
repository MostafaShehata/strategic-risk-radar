from langgraph.graph import END, StateGraph

from .agents import EnrichmentWorkflowAgents
from .models import EnrichmentState


def build_graph(nodes: EnrichmentWorkflowAgents):
    graph = StateGraph(EnrichmentState)
    graph.add_node("load_raw_article", nodes.load_raw_article)
    graph.add_node("normalize", nodes.normalize)
    graph.add_node("entity_extraction", nodes.entity_extraction)
    graph.add_node("geo_transport_resolver", nodes.resolve_geo_transport)
    graph.add_node("path_impact", nodes.path_impact)
    graph.add_node("kpi_impact", nodes.kpi_impact)
    graph.add_node("risk_scoring", nodes.risk_scoring)
    graph.add_node("topic_clustering", nodes.topic_clustering)
    graph.add_node("final_validator", nodes.final_validator)
    graph.add_node("save_enriched_article", nodes.save_enriched_article)
    graph.add_node("rag_index", nodes.rag_index)

    graph.set_entry_point("load_raw_article")
    graph.add_edge("load_raw_article", "normalize")
    graph.add_edge("normalize", "entity_extraction")
    graph.add_edge("entity_extraction", "geo_transport_resolver")
    graph.add_edge("geo_transport_resolver", "path_impact")
    graph.add_edge("path_impact", "kpi_impact")
    graph.add_edge("kpi_impact", "risk_scoring")
    graph.add_edge("risk_scoring", "topic_clustering")
    graph.add_edge("topic_clustering", "final_validator")
    graph.add_edge("final_validator", "save_enriched_article")
    graph.add_edge("save_enriched_article", "rag_index")
    graph.add_edge("rag_index", END)
    return graph.compile()
