import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from psycopg.rows import dict_row


app = FastAPI(title="Strategic Risk Radar Command Center API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
        return connection.execute(sql, params).fetchall()


def first(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows = query(sql, params)
    return rows[0] if rows else {}


def rag_search(text: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rag_url = os.environ.get("RAG_API_URL", "http://rag-api:8100").rstrip("/")
    payload = json.dumps({"query": text, "top_k": top_k, "filters": filters or {}}).encode("utf-8")
    request = Request(
        f"{rag_url}/api/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("hits", [])
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return []


class SimulationRequest(BaseModel):
    topic_id: str | None = None
    scenario: str
    severity: int = 70
    duration_days: int = 30


class TopicChatRequest(BaseModel):
    topic_id: str
    question: str
    top_k: int = 5


@app.get("/api/health")
def health() -> dict[str, str]:
    query("SELECT 1")
    return {"status": "ok"}


@app.get("/api/use-cases")
def use_cases() -> dict[str, list[dict[str, str]]]:
    return {
        "implemented": [
            {"name": "Executive dashboard", "basis": "Raw/enriched counts, topic risk, KPI impact, RAG status."},
            {"name": "Trending events", "basis": "LLM-generated topics, article counts, risk scores, UAE impact."},
            {"name": "360 impact view", "basis": "Topic detail, KPI impacts, entities, related articles, path impacts."},
            {"name": "Briefing report", "basis": "Highest-risk topics and recommendations synthesized from stored enrichment output."},
            {"name": "Topic chatbot", "basis": "RAG search over indexed enriched news chunks for the selected topic/question."},
            {"name": "What-if simulator", "basis": "Rule-based projection from selected topic risk, KPI scores, severity, and duration."},
        ],
        "needs_internal_data": [
            {"name": "Cargo financial exposure", "basis": "Needs ICP/customs cargo value, manifest, shipment, carrier, and route datasets."},
            {"name": "Passenger exposure", "basis": "Needs passenger/API/PNR movement data and airport operational datasets."},
            {"name": "Visa/residency pressure", "basis": "Needs identity, visa validity, overstay, nationality, and exit/entry history."},
            {"name": "Action approval workflow", "basis": "Needs user management, delegation matrix, audit trail, and official decision workflow."},
            {"name": "Real operational recommendations", "basis": "Needs approved ICP policy/rule books and authority-specific playbooks."},
        ],
    }


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    overview = first(
        """SELECT (SELECT count(*) FROM raw_news_items) AS raw_documents,
                  (SELECT count(*) FROM enriched_news_items) AS enriched_documents,
                  (SELECT count(*) FROM topics) AS active_topics,
                  (SELECT count(*) FROM topics WHERE risk_level IN ('high','critical')) AS high_risk_topics,
                  (SELECT count(*) FROM news_kpi_impacts) AS kpi_impacts,
                  (SELECT count(*) FROM enrichment_runs WHERE status='running') AS enrichment_running,
                  (SELECT count(*) FROM source_runs WHERE status='running') AS ingestion_running"""
    )
    top_events = events(limit=6)
    kpis = query(
        """SELECT kpi_name,
                  count(*) AS article_count,
                  round(avg(risk_score),1) AS average_risk_score,
                  max(risk_score) AS highest_risk_score,
                  count(*) FILTER (WHERE risk_level='critical') AS critical_count,
                  count(*) FILTER (WHERE risk_level='high') AS high_count
           FROM news_kpi_impacts
           GROUP BY kpi_name
           ORDER BY highest_risk_score DESC, article_count DESC
           LIMIT 8"""
    )
    activity = query(
        """SELECT e.id,e.title,e.source_id,e.risk_score,e.risk_level,e.created_at,
                  t.id AS topic_id,t.title AS topic_title
           FROM enriched_news_items e
           LEFT JOIN topic_articles ta ON ta.enriched_news_item_id=e.id
           LEFT JOIN topics t ON t.id=ta.topic_id
           ORDER BY e.created_at DESC LIMIT 10"""
    )
    return {"overview": overview, "top_events": top_events, "kpis": kpis, "activity": activity}


@app.get("/api/events")
def events(limit: int = 30, risk_level: str = "", search: str = "") -> list[dict[str, Any]]:
    return query(
        """SELECT t.id,t.title,t.summary,t.risk_score,t.risk_level,t.event_type,t.uae_impact,
                  t.primary_countries,t.primary_domains,t.affected_kpis,t.created_at,t.updated_at,
                  count(ta.enriched_news_item_id) AS article_count,
                  max(e.created_at) AS latest_article_at,
                  coalesce(max(e.risk_score), t.risk_score) AS highest_article_risk
           FROM topics t
           LEFT JOIN topic_articles ta ON ta.topic_id=t.id
           LEFT JOIN enriched_news_items e ON e.id=ta.enriched_news_item_id
           WHERE (%s='' OR t.risk_level=%s)
             AND (%s='' OR t.title ILIKE '%%'||%s||'%%' OR t.summary ILIKE '%%'||%s||'%%')
           GROUP BY t.id
           ORDER BY highest_article_risk DESC, latest_article_at DESC NULLS LAST
           LIMIT %s""",
        (risk_level, risk_level, search, search, search, limit),
    )


@app.get("/api/events/{topic_id}")
def event_detail(topic_id: str) -> dict[str, Any]:
    topic = first(
        """SELECT id,title,summary,status,risk_score,risk_level,topic_key,event_type,uae_impact,
                  primary_countries,primary_domains,affected_kpis,created_at,updated_at
           FROM topics WHERE id=%s""",
        (topic_id,),
    )
    articles = query(
        """SELECT e.id,e.title,e.summary,e.source_id,e.source_type,n.url,e.publication_date,
                  e.risk_score,e.risk_level,e.risk_reason,e.risk_domains,ta.similarity_score,
                  ta.llm_match_confidence,ta.is_primary_article
           FROM topic_articles ta
           JOIN enriched_news_items e ON e.id=ta.enriched_news_item_id
           JOIN raw_news_items n ON n.id=e.raw_news_item_id
           WHERE ta.topic_id=%s
           ORDER BY ta.is_primary_article DESC,e.risk_score DESC,e.created_at DESC
           LIMIT 50""",
        (topic_id,),
    )
    kpis = query(
        """SELECT k.kpi_name,count(*) AS article_count,round(avg(k.risk_score),1) AS average_risk_score,
                  max(k.risk_score) AS highest_risk_score,max(k.risk_level) AS highest_risk_level,
                  string_agg(DISTINCT k.impact_summary, ' | ') AS impact_summary
           FROM news_kpi_impacts k
           JOIN topic_articles ta ON ta.enriched_news_item_id=k.enriched_news_item_id
           WHERE ta.topic_id=%s
           GROUP BY k.kpi_name
           ORDER BY highest_risk_score DESC,k.kpi_name""",
        (topic_id,),
    )
    entities = query(
        """SELECT ent.entity_type,ent.normalized_name AS name,ent.code,count(*) AS mentions
           FROM news_entities ent
           JOIN topic_articles ta ON ta.enriched_news_item_id=ent.enriched_news_item_id
           WHERE ta.topic_id=%s
           GROUP BY ent.entity_type,ent.normalized_name,ent.code
           ORDER BY mentions DESC,ent.entity_type LIMIT 40""",
        (topic_id,),
    )
    paths = query(
        """SELECT p.path_code,p.impact_type,p.impact_level,p.reason,count(*) AS mentions
           FROM news_path_impacts p
           JOIN topic_articles ta ON ta.enriched_news_item_id=p.enriched_news_item_id
           WHERE ta.topic_id=%s
           GROUP BY p.path_code,p.impact_type,p.impact_level,p.reason
           ORDER BY mentions DESC,p.impact_level LIMIT 30""",
        (topic_id,),
    )
    return {"topic": topic, "articles": articles, "kpis": kpis, "entities": entities, "paths": paths}


@app.get("/api/briefing")
def briefing() -> dict[str, Any]:
    top_events = events(limit=5)
    recommendations = []
    for event in top_events:
        domains = event.get("primary_domains") or []
        affected = event.get("affected_kpis") or []
        recommendations.append(
            {
                "topic_id": event["id"],
                "title": f"Review response posture for {event['title']}",
                "priority": event["risk_level"],
                "rationale": event.get("uae_impact") or event.get("summary") or "High-risk topic requires executive review.",
                "domains": domains,
                "affected_kpis": affected,
            }
        )
    return {"title": "Daily ICP Global Risk Brief", "top_events": top_events, "recommendations": recommendations}


@app.post("/api/simulation")
def simulation(request: SimulationRequest) -> dict[str, Any]:
    topic = event_detail(request.topic_id)["topic"] if request.topic_id else {}
    base_score = int(topic.get("risk_score") or request.severity)
    duration_factor = min(1.6, max(0.5, request.duration_days / 30))
    projected_score = min(100, round((base_score * 0.65 + request.severity * 0.35) * duration_factor))
    level = "critical" if projected_score >= 75 else "high" if projected_score >= 50 else "medium" if projected_score >= 25 else "low"
    return {
        "scenario": request.scenario,
        "topic": topic,
        "projected_score": projected_score,
        "projected_level": level,
        "duration_days": request.duration_days,
        "assumptions": [
            "Projection uses current topic risk and KPI impact rows from the PoC database.",
            "No internal cargo, passenger, visa, or staffing datasets are included yet.",
        ],
        "decision_matrix": [
            {"option": "Executive monitoring", "benefit": "Keeps leadership aligned", "risk": "Low operational cost", "confidence": 0.82},
            {"option": "Targeted source review", "benefit": "Validates article evidence", "risk": "Requires analyst time", "confidence": 0.74},
            {"option": "Operational playbook mapping", "benefit": "Connects event to ICP actions", "risk": "Needs internal policies", "confidence": 0.58},
        ],
    }


@app.post("/api/topic-chat")
def topic_chat(request: TopicChatRequest) -> dict[str, Any]:
    topic = event_detail(request.topic_id)["topic"]
    query_text = f"{topic.get('title', '')} {request.question}".strip()
    hits = rag_search(query_text, request.top_k)
    evidence = [
        {
            "score": hit.get("score"),
            "source": hit.get("source"),
            "text": hit.get("text", "")[:700],
            "metadata": hit.get("metadata", {}),
        }
        for hit in hits
    ]
    answer = (
        "I found related indexed evidence in RAG. Review the cited snippets below; a later LLM answer layer can "
        "turn this into a fully generated response with policy grounding."
        if evidence
        else "No indexed RAG evidence was returned for this topic/question yet."
    )
    return {"topic": topic, "question": request.question, "answer": answer, "evidence": evidence}
