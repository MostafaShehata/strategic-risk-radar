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


@app.get("/api/health")
def health() -> dict[str, str]:
    query("SELECT 1")
    return {"status": "ok"}


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    return query(
        """SELECT count(*) AS total_runs,
                  count(*) FILTER (WHERE status='completed') AS completed_runs,
                  count(*) FILTER (WHERE status='running') AS running_runs,
                  count(*) FILTER (WHERE status='completed_with_errors') AS runs_with_errors,
                  coalesce(sum(total_inserted),0) AS total_inserted,
                  (SELECT count(*) FROM raw_news_items) AS total_documents
           FROM ingestion_runs"""
    )[0]


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
