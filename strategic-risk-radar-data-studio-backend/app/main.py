import os
from typing import Any

import psycopg
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row


app = FastAPI(title="Strategic Risk Radar Data Studio API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
        return connection.execute(sql, params).fetchall()


def scalar(sql: str, params: tuple[Any, ...] = ()) -> Any:
    rows = query(sql, params)
    return rows[0]["value"] if rows else None


@app.get("/api/health")
def health() -> dict[str, str]:
    query("SELECT 1")
    return {"status": "ok"}


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    row = query(
        """SELECT count(*) AS total_runs,
                  count(*) FILTER (WHERE status='completed') AS completed_runs,
                  count(*) FILTER (WHERE status='running') AS running_runs,
                  count(*) FILTER (WHERE status='completed_with_errors') AS runs_with_errors,
                  coalesce(sum(total_inserted),0) AS total_inserted,
                  (SELECT count(*) FROM raw_news_items) AS total_documents
           FROM ingestion_runs"""
    )[0]
    enrichment = query(
        """SELECT count(*) AS enrichment_runs,
                  count(*) FILTER (WHERE status='running') AS enrichment_running,
                  coalesce(sum(processed_count),0) AS enrichment_processed,
                  coalesce(sum(success_count),0) AS enrichment_success,
                  coalesce(sum(failed_count),0) AS enrichment_failed,
                  (SELECT count(*) FROM enriched_news_items) AS enriched_documents,
                  (SELECT count(*) FROM topics) AS topics,
                  (SELECT count(*) FROM news_kpi_impacts) AS kpi_impacts,
                  (SELECT count(*) FROM raw_news_items WHERE processing_status='pending') AS pending_enrichment
           FROM enrichment_runs"""
    )[0]
    return {**row, **enrichment}


@app.get("/api/runs")
def runs(
    limit: int = Query(20, ge=1, le=200),
    source_type: str = "",
    status: str = "",
) -> list[dict[str, Any]]:
    return query(
        """SELECT r.id,r.started_at,r.completed_at,r.status,r.total_retrieved,r.total_matched,
                  r.total_inserted,r.total_duplicates,r.error_count,
                  s.id AS source_run_id,s.source_id,s.source_type,s.duration_ms
           FROM ingestion_runs r
           LEFT JOIN LATERAL (
               SELECT id,source_id,source_type,duration_ms
               FROM source_runs
               WHERE run_id=r.id
               ORDER BY started_at
               LIMIT 1
           ) s ON true
           WHERE (%s='' OR s.source_type=%s)
             AND (%s='' OR r.status=%s)
           ORDER BY r.started_at DESC LIMIT %s""",
        (source_type, source_type, status, status, limit),
    )


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    run_rows = query(
        """SELECT id,started_at,completed_at,status,total_retrieved,total_matched,
                  total_inserted,total_duplicates,error_count,config_snapshot
           FROM ingestion_runs WHERE id=%s""",
        (run_id,),
    )
    sources = query(
        """SELECT id,source_id,source_type,status,window_start,window_end,request_count,
                  retrieved_count,matched_count,inserted_count,duplicate_count,
                  duration_ms,error_message
           FROM source_runs WHERE run_id=%s ORDER BY started_at,source_id""",
        (run_id,),
    )
    source_ids = [source["id"] for source in sources]
    keyword_rows = query(
        """SELECT source_run_id,keyword,request_count,retrieved_count,matched_count,
                  inserted_count,duplicate_count
           FROM keyword_run_metrics WHERE source_run_id=ANY(%s) ORDER BY keyword""",
        (source_ids,),
    ) if source_ids else []
    keyword_map: dict[int, list[dict[str, Any]]] = {}
    for keyword in keyword_rows:
        keyword_map.setdefault(keyword["source_run_id"], []).append(keyword)
    for source in sources:
        source["keywords"] = keyword_map.get(source["id"], [])
    return {"run": run_rows[0] if run_rows else None, "sources": sources}


@app.get("/api/sources")
def sources(
    limit: int = Query(50, ge=1, le=500),
    source_type: str = "",
    status: str = "",
) -> list[dict[str, Any]]:
    return query(
        """SELECT id,run_id,source_id,status,window_start,window_end,request_count,retrieved_count,
                  matched_count,inserted_count,duplicate_count,duration_ms,error_message,source_type
           FROM source_runs
           WHERE source_type <> 'reliefweb'
             AND (%s='' OR source_type=%s)
             AND (%s='' OR status=%s)
           ORDER BY started_at DESC LIMIT %s""",
        (source_type, source_type, status, status, limit),
    )


@app.get("/api/keywords")
def keywords(limit: int = Query(100, ge=1, le=1000)) -> list[dict[str, Any]]:
    return query(
        """SELECT s.run_id,s.id AS source_run_id,s.source_id,k.keyword,k.request_count,k.retrieved_count,
                  k.matched_count,k.inserted_count,k.duplicate_count
           FROM keyword_run_metrics k JOIN source_runs s ON s.id=k.source_run_id
           ORDER BY s.started_at DESC,k.keyword LIMIT %s""",
        (limit,),
    )


@app.get("/api/documents")
def documents(
    search: str = "",
    source: str = "",
    keyword: str = "",
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return query(
        """SELECT id,source_id,title,url,summary,body,published_at,first_seen_at,
                  processing_status,keywords
           FROM v_documents_browse d
           WHERE (%s='' OR source_id=%s)
             AND (%s='' OR EXISTS (
                 SELECT 1 FROM raw_news_item_keywords k
                 WHERE k.item_id=d.id AND k.keyword=%s
             ))
             AND (%s='' OR title ILIKE '%%'||%s||'%%' OR summary ILIKE '%%'||%s||'%%')
           ORDER BY coalesce(published_at,first_seen_at) DESC LIMIT %s""",
        (source, source, keyword, keyword, search, search, search, limit),
    )


@app.get("/api/source-types")
def source_types() -> list[dict[str, Any]]:
    return query(
        """SELECT DISTINCT source_type
           FROM source_runs
           WHERE source_type IS NOT NULL
             AND source_type <> 'reliefweb'
           ORDER BY source_type"""
    )


@app.get("/api/document-keywords")
def document_keywords() -> list[dict[str, Any]]:
    return query(
        """SELECT DISTINCT keyword
           FROM raw_news_item_keywords
           ORDER BY keyword"""
    )


@app.get("/api/enrichment/overview")
def enrichment_overview() -> dict[str, Any]:
    return query(
        """SELECT (SELECT count(*) FROM enriched_news_items) AS enriched_documents,
                  (SELECT count(*) FROM enriched_news_items WHERE enrichment_status='needs_review') AS needs_review,
                  (SELECT count(*) FROM topics) AS topics,
                  (SELECT count(*) FROM news_kpi_impacts) AS kpi_impacts,
                  (SELECT count(*) FROM news_path_impacts) AS path_impacts,
                  (SELECT count(*) FROM raw_news_items WHERE processing_status='pending') AS pending_documents,
                  (SELECT count(*) FROM raw_news_items WHERE processing_status='enriching') AS enriching_documents,
                  (SELECT count(*) FROM enrichment_runs WHERE status='running') AS running_enrichment_runs,
                  coalesce((SELECT round(avg(risk_score),1) FROM enriched_news_items),0) AS average_risk_score,
                  coalesce((SELECT max(risk_score) FROM enriched_news_items),0) AS highest_risk_score"""
    )[0]


@app.get("/api/enrichment/runs")
def enrichment_runs(
    limit: int = Query(30, ge=1, le=200),
    status: str = "",
) -> list[dict[str, Any]]:
    return query(
        """SELECT id,started_at,completed_at,status,processed_count,success_count,failed_count,
                  model_name,error_message,
                  EXTRACT(EPOCH FROM coalesce(completed_at, now()) - started_at)::integer AS duration_seconds
           FROM enrichment_runs
           WHERE (%s='' OR status=%s)
           ORDER BY started_at DESC LIMIT %s""",
        (status, status, limit),
    )


@app.get("/api/enrichment/runs/{run_id}")
def enrichment_run_detail(run_id: str) -> dict[str, Any]:
    run_rows = query(
        """SELECT id,started_at,completed_at,status,processed_count,success_count,failed_count,
                  model_name,error_message,
                  EXTRACT(EPOCH FROM coalesce(completed_at, now()) - started_at)::integer AS duration_seconds
           FROM enrichment_runs WHERE id=%s""",
        (run_id,),
    )
    items = query(
        """SELECT e.id,e.raw_news_item_id,e.title,e.source_id,e.source_type,e.publication_date,
                  e.risk_score,e.risk_level,e.risk_domains,e.enrichment_status,e.body_source,
                  e.confidence_score,e.created_at
           FROM enriched_news_items e
           JOIN enrichment_runs r ON r.id=%s
           WHERE e.created_at >= r.started_at
             AND e.created_at <= coalesce(r.completed_at, now()) + interval '5 seconds'
           ORDER BY e.created_at DESC""",
        (run_id,),
    )
    return {"run": run_rows[0] if run_rows else None, "items": items}


@app.get("/api/enrichment/items")
def enriched_items(
    search: str = "",
    source: str = "",
    risk_level: str = "",
    status: str = "",
    domain: str = "",
    topic_id: str = "",
    keyword: str = "",
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return query(
        """SELECT e.id,e.raw_news_item_id,e.title,e.summary,e.source_id,e.source_type,n.url,
                  e.publication_date,e.language,e.body_source,e.risk_score,e.risk_level,
                  e.risk_domains,e.risk_reason,e.confidence_score,e.enrichment_status,
                  e.countries,e.cities,e.airports,e.ports,e.airlines,e.companies,
                  e.organizations,e.persons,e.military_groups,e.government_agencies,
                  e.created_at,e.updated_at,
                  t.id AS topic_id,t.title AS topic_title,
                  coalesce(pi.path_count,0) AS path_impact_count,
                  coalesce(ne.entity_count,0) AS entity_count,
                  coalesce(ki.kpi_count,0) AS kpi_impact_count,
                  string_agg(DISTINCT k.keyword, ', ' ORDER BY k.keyword) AS keywords
           FROM enriched_news_items e
           JOIN raw_news_items n ON n.id=e.raw_news_item_id
           LEFT JOIN topic_articles ta ON ta.enriched_news_item_id=e.id
           LEFT JOIN topics t ON t.id=ta.topic_id
           LEFT JOIN raw_news_item_keywords k ON k.item_id=n.id
           LEFT JOIN LATERAL (
               SELECT count(*) AS path_count FROM news_path_impacts p WHERE p.enriched_news_item_id=e.id
           ) pi ON true
           LEFT JOIN LATERAL (
               SELECT count(*) AS entity_count FROM news_entities ent WHERE ent.enriched_news_item_id=e.id
           ) ne ON true
           LEFT JOIN LATERAL (
               SELECT count(*) AS kpi_count FROM news_kpi_impacts kpi WHERE kpi.enriched_news_item_id=e.id
           ) ki ON true
           WHERE e.risk_score >= %s
             AND (%s='' OR e.source_id=%s)
             AND (%s='' OR e.risk_level=%s)
             AND (%s='' OR e.enrichment_status=%s)
             AND (%s='' OR e.risk_domains ? %s)
             AND (%s='' OR t.id::text=%s)
             AND (%s='' OR EXISTS (
                 SELECT 1 FROM raw_news_item_keywords kw
                 WHERE kw.item_id=n.id AND kw.keyword=%s
             ))
             AND (%s='' OR e.title ILIKE '%%'||%s||'%%'
                  OR e.summary ILIKE '%%'||%s||'%%'
                  OR e.normalized_body ILIKE '%%'||%s||'%%')
           GROUP BY e.id,n.url,t.id,pi.path_count,ne.entity_count,ki.kpi_count
           ORDER BY e.risk_score DESC, coalesce(e.publication_date,e.created_at) DESC
           LIMIT %s""",
        (
            min_score,
            source, source,
            risk_level, risk_level,
            status, status,
            domain, domain,
            topic_id, topic_id,
            keyword, keyword,
            search, search, search, search,
            limit,
        ),
    )


@app.get("/api/enrichment/items/{item_id}")
def enriched_item_detail(item_id: str) -> dict[str, Any]:
    item_rows = query(
        """SELECT e.*, n.url, n.first_seen_at, n.processing_status AS raw_processing_status,
                  string_agg(DISTINCT k.keyword, ', ' ORDER BY k.keyword) AS keywords,
                  t.id AS topic_id,t.title AS topic_title,t.summary AS topic_summary
           FROM enriched_news_items e
           JOIN raw_news_items n ON n.id=e.raw_news_item_id
           LEFT JOIN raw_news_item_keywords k ON k.item_id=n.id
           LEFT JOIN topic_articles ta ON ta.enriched_news_item_id=e.id
           LEFT JOIN topics t ON t.id=ta.topic_id
           WHERE e.id=%s
           GROUP BY e.id,n.id,t.id""",
        (item_id,),
    )
    entities = query(
        """SELECT entity_type,name,normalized_name,code,country_code,confidence_score
           FROM news_entities WHERE enriched_news_item_id=%s
           ORDER BY entity_type,name""",
        (item_id,),
    )
    paths = query(
        """SELECT origin,destination,path_code,impact_type,impact_level,reason,confidence_score
           FROM news_path_impacts WHERE enriched_news_item_id=%s
           ORDER BY impact_level,path_code""",
        (item_id,),
    )
    kpis = query(
        """SELECT kpi_name,risk_score,risk_level,impact_summary,evidence,confidence_score
           FROM news_kpi_impacts WHERE enriched_news_item_id=%s
           ORDER BY risk_score DESC,kpi_name""",
        (item_id,),
    )
    fetches = query(
        """SELECT url,status,fetcher,title,language,published_at,error_message,created_at,
                  length(body) AS body_length
           FROM article_content_fetches
           WHERE raw_news_item_id=(SELECT raw_news_item_id FROM enriched_news_items WHERE id=%s)
           ORDER BY created_at DESC""",
        (item_id,),
    )
    return {
        "item": item_rows[0] if item_rows else None,
        "entities": entities,
        "path_impacts": paths,
        "kpi_impacts": kpis,
        "content_fetches": fetches,
    }


@app.get("/api/enrichment/topics")
def topics(
    search: str = "",
    risk_level: str = "",
    domain: str = "",
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return query(
        """SELECT t.id,t.title,t.summary,t.status,t.risk_score,t.risk_level,t.topic_key,
                  t.event_type,t.uae_impact,t.primary_countries,t.primary_domains,t.affected_kpis,
                  t.signature,t.created_at,t.updated_at,
                  count(ta.enriched_news_item_id) AS article_count,
                  max(e.created_at) AS latest_article_at,
                  coalesce(max(e.risk_score), t.risk_score) AS highest_article_risk
           FROM topics t
           LEFT JOIN topic_articles ta ON ta.topic_id=t.id
           LEFT JOIN enriched_news_items e ON e.id=ta.enriched_news_item_id
           WHERE t.topic_key <> ''
             AND (%s='' OR t.risk_level=%s)
             AND (%s='' OR t.primary_domains ? %s)
             AND (%s='' OR t.title ILIKE '%%'||%s||'%%' OR t.summary ILIKE '%%'||%s||'%%')
           GROUP BY t.id
           ORDER BY highest_article_risk DESC, latest_article_at DESC NULLS LAST
           LIMIT %s""",
        (risk_level, risk_level, domain, domain, search, search, search, limit),
    )


@app.get("/api/enrichment/topics/{topic_id}")
def topic_detail(topic_id: str) -> dict[str, Any]:
    topic_rows = query(
        """SELECT id,title,summary,status,risk_score,risk_level,topic_key,event_type,
                  uae_impact,primary_countries,primary_domains,affected_kpis,signature,created_at,updated_at
           FROM topics WHERE id=%s""",
        (topic_id,),
    )
    articles = query(
        """SELECT e.id,e.title,e.source_id,e.source_type,e.publication_date,e.risk_score,
                  e.risk_level,e.risk_domains,e.risk_reason,ta.similarity_score,
                  ta.llm_match_confidence,ta.is_primary_article
           FROM topic_articles ta
           JOIN enriched_news_items e ON e.id=ta.enriched_news_item_id
           WHERE ta.topic_id=%s
           ORDER BY ta.is_primary_article DESC,e.risk_score DESC,e.created_at DESC""",
        (topic_id,),
    )
    return {"topic": topic_rows[0] if topic_rows else None, "articles": articles}


@app.get("/api/enrichment/kpis")
def kpi_dashboard(
    source: str = "",
    topic_id: str = "",
    risk_level: str = "",
) -> list[dict[str, Any]]:
    return query(
        """SELECT k.kpi_name,
                  count(*) AS article_count,
                  round(avg(k.risk_score),1) AS average_risk_score,
                  max(k.risk_score) AS highest_risk_score,
                  count(*) FILTER (WHERE k.risk_level='critical') AS critical_count,
                  count(*) FILTER (WHERE k.risk_level='high') AS high_count,
                  count(*) FILTER (WHERE k.risk_level='medium') AS medium_count,
                  count(*) FILTER (WHERE k.risk_level='low') AS low_count,
                  max(e.created_at) AS latest_article_at
           FROM news_kpi_impacts k
           JOIN enriched_news_items e ON e.id=k.enriched_news_item_id
           LEFT JOIN topic_articles ta ON ta.enriched_news_item_id=e.id
           WHERE (%s='' OR e.source_id=%s)
             AND (%s='' OR ta.topic_id::text=%s)
             AND (%s='' OR k.risk_level=%s)
           GROUP BY k.kpi_name
           ORDER BY highest_risk_score DESC, article_count DESC,k.kpi_name""",
        (source, source, topic_id, topic_id, risk_level, risk_level),
    )


@app.get("/api/enrichment/filter-options")
def enrichment_filter_options() -> dict[str, list[str]]:
    source_rows = query("SELECT DISTINCT source_id AS value FROM enriched_news_items ORDER BY source_id")
    domain_rows = query(
        """SELECT DISTINCT jsonb_array_elements_text(risk_domains) AS value
           FROM enriched_news_items ORDER BY value"""
    )
    risk_rows = query("SELECT DISTINCT risk_level AS value FROM enriched_news_items ORDER BY risk_level")
    status_rows = query("SELECT DISTINCT enrichment_status AS value FROM enriched_news_items ORDER BY enrichment_status")
    return {
        "sources": [row["value"] for row in source_rows],
        "domains": [row["value"] for row in domain_rows],
        "risk_levels": [row["value"] for row in risk_rows],
        "statuses": [row["value"] for row in status_rows],
    }
