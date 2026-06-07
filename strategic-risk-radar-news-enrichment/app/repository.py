import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .models import EnrichmentState, Entity, KpiImpact, PathImpact, RawArticle


class EnrichmentRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def begin_run(self, model_name: str) -> UUID:
        with psycopg.connect(self.database_url) as connection:
            return connection.execute(
                "INSERT INTO enrichment_runs(model_name) VALUES (%s) RETURNING id",
                (model_name,),
            ).fetchone()[0]

    def finish_run(self, run_id: UUID, processed: int, success: int, failed: int, error: str | None = None) -> None:
        status = "completed" if not error else "completed_with_errors"
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """UPDATE enrichment_runs
                   SET completed_at=now(),status=%s,processed_count=%s,success_count=%s,
                       failed_count=%s,error_message=%s
                   WHERE id=%s""",
                (status, processed, success, failed, error, run_id),
            )

    def reset_stale_claims(self, timeout_seconds: int) -> int:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """UPDATE raw_news_items
                   SET processing_status='pending',
                       enrichment_run_id=NULL,
                       enrichment_claimed_at=NULL
                   WHERE processing_status='enriching'
                     AND (
                       enrichment_claimed_at IS NULL
                       OR enrichment_claimed_at < now() - (%s || ' seconds')::interval
                     )
                   RETURNING id""",
                (timeout_seconds,),
            ).fetchall()
        return len(row)

    def claim_articles(self, batch_size: int, run_id: UUID) -> list[RawArticle]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """WITH candidates AS (
                       SELECT id FROM raw_news_items
                       WHERE processing_status IN ('pending','enrichment_failed')
                         AND NOT EXISTS (
                           SELECT 1 FROM enriched_news_items e WHERE e.raw_news_item_id=raw_news_items.id
                         )
                       ORDER BY first_seen_at
                       LIMIT %s
                       FOR UPDATE SKIP LOCKED
                   )
                   UPDATE raw_news_items n
                   SET processing_status='enriching',
                       enrichment_run_id=%s,
                       enrichment_claimed_at=now()
                   FROM candidates c
                   WHERE n.id=c.id
                   RETURNING n.*""",
                (batch_size, run_id),
            ).fetchall()
        return [self.raw_article(row) for row in rows]

    def raw_article(self, row: dict[str, Any]) -> RawArticle:
        return RawArticle(
            id=row["id"],
            source_id=row["source_id"],
            source_type=row["source_type"],
            url=row["url"],
            title=row["title"],
            summary=row["summary"],
            body=row["body"],
            published_at=row["published_at"],
            raw_payload=row["raw_payload"],
        )

    def save_content_fetch(self, raw_id: UUID, url: str, result: dict[str, Any]) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """INSERT INTO article_content_fetches
                   (raw_news_item_id,url,status,fetcher,title,body,language,published_at,error_message)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    raw_id,
                    url,
                    result.get("status", "failed"),
                    result.get("fetcher", "unknown"),
                    result.get("title", ""),
                    result.get("body", ""),
                    result.get("language"),
                    result.get("published_at") or None,
                    result.get("error_message"),
                ),
            )

    def save_enrichment(self, state: EnrichmentState, model_name: str) -> UUID:
        raw = state["raw"]
        with psycopg.connect(self.database_url) as connection:
            enriched_id = connection.execute(
                """INSERT INTO enriched_news_items
                   (raw_news_item_id,title,summary,publication_date,source_id,source_type,language,
                    normalized_body,body_source,countries,cities,airports,ports,airlines,companies,
                    organizations,persons,military_groups,government_agencies,risk_score,risk_level,
                    risk_domains,risk_reason,confidence_score,enrichment_status,model_name,trace)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,
                           %s::jsonb,%s,%s,%s,%s,%s::jsonb)
                   ON CONFLICT(raw_news_item_id) DO UPDATE SET
                     title=EXCLUDED.title,summary=EXCLUDED.summary,publication_date=EXCLUDED.publication_date,
                     language=EXCLUDED.language,normalized_body=EXCLUDED.normalized_body,
                     body_source=EXCLUDED.body_source,risk_score=EXCLUDED.risk_score,
                     risk_level=EXCLUDED.risk_level,risk_domains=EXCLUDED.risk_domains,
                     risk_reason=EXCLUDED.risk_reason,confidence_score=EXCLUDED.confidence_score,
                     enrichment_status=EXCLUDED.enrichment_status,trace=EXCLUDED.trace,updated_at=now()
                   RETURNING id""",
                (
                    raw.id,
                    state.get("title", raw.title),
                    state.get("summary", raw.summary),
                    state.get("publication_date"),
                    raw.source_id,
                    raw.source_type,
                    state.get("language", "unknown"),
                    state.get("normalized_body", ""),
                    state.get("body_source", "unknown"),
                    self.entity_names(state, "countries"),
                    self.entity_names(state, "cities"),
                    self.entity_names(state, "airports"),
                    self.entity_names(state, "ports"),
                    self.entity_names(state, "airlines"),
                    self.entity_names(state, "companies"),
                    self.entity_names(state, "organizations"),
                    self.entity_names(state, "persons"),
                    self.entity_names(state, "military_groups"),
                    self.entity_names(state, "government_agencies"),
                    state.get("risk_score", 0),
                    state.get("risk_level", "low"),
                    json.dumps(state.get("risk_domains", [])),
                    state.get("risk_reason", ""),
                    state.get("confidence_score", 0),
                    state.get("enrichment_status", "completed"),
                    model_name,
                    json.dumps(state.get("trace", {}), default=str),
                ),
            ).fetchone()[0]
            connection.execute("DELETE FROM news_entities WHERE enriched_news_item_id=%s", (enriched_id,))
            connection.execute("DELETE FROM news_path_impacts WHERE enriched_news_item_id=%s", (enriched_id,))
            connection.execute("DELETE FROM news_kpi_impacts WHERE enriched_news_item_id=%s", (enriched_id,))
            self.insert_entities(connection, enriched_id, state)
            self.insert_path_impacts(connection, enriched_id, state.get("path_impacts", []))
            self.insert_kpi_impacts(connection, enriched_id, state.get("kpi_impacts", []))
            self.save_topic_link(connection, enriched_id, state)
            connection.execute(
                """UPDATE raw_news_items
                   SET processing_status=%s,
                       enrichment_run_id=NULL,
                       enrichment_claimed_at=NULL
                   WHERE id=%s""",
                (state.get("enrichment_status", "enriched"), raw.id),
            )
            return enriched_id

    def mark_failed(self, raw_id: UUID, error: str) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """UPDATE raw_news_items
                   SET processing_status='enrichment_failed',
                       enrichment_run_id=NULL,
                       enrichment_claimed_at=NULL
                   WHERE id=%s""",
                (raw_id,),
            )

    def entity_names(self, state: EnrichmentState, key: str) -> str:
        return json.dumps([entity.name for entity in state.get("entities", {}).get(key, [])])

    def insert_entities(self, connection, enriched_id: UUID, state: EnrichmentState) -> None:
        for entity_type, entities in state.get("entities", {}).items():
            for entity in entities:
                connection.execute(
                    """INSERT INTO news_entities
                       (enriched_news_item_id,entity_type,name,normalized_name,code,country_code,confidence_score)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        enriched_id,
                        entity_type,
                        entity.name,
                        entity.normalized_name,
                        entity.code,
                        entity.country_code,
                        entity.confidence_score,
                    ),
                )

    def insert_path_impacts(self, connection, enriched_id: UUID, impacts: list[PathImpact]) -> None:
        for impact in impacts:
            connection.execute(
                """INSERT INTO news_path_impacts
                   (enriched_news_item_id,origin,destination,path_code,impact_type,impact_level,reason,confidence_score)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    enriched_id,
                    impact.origin,
                    impact.destination,
                    impact.path_code,
                    impact.impact_type,
                    impact.impact_level,
                    impact.reason,
                    impact.confidence_score,
                ),
            )

    def insert_kpi_impacts(self, connection, enriched_id: UUID, impacts: list[KpiImpact]) -> None:
        for impact in impacts:
            connection.execute(
                """INSERT INTO news_kpi_impacts
                   (enriched_news_item_id,kpi_name,risk_score,risk_level,impact_summary,evidence,confidence_score)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    enriched_id,
                    impact.kpi_name,
                    impact.risk_score,
                    impact.risk_level,
                    impact.impact_summary,
                    impact.evidence,
                    impact.confidence_score,
                ),
            )

    def save_topic_link(self, connection, enriched_id: UUID, state: EnrichmentState) -> None:
        topic = state.get("topic")
        if not topic or not (topic.topic_key or topic.title):
            return
        affected_kpis = json.dumps(topic.affected_kpis or [impact.kpi_name for impact in state.get("kpi_impacts", [])])
        topic_id = topic.topic_id or connection.execute(
            """INSERT INTO topics(title,summary,risk_score,risk_level,topic_key,event_type,uae_impact,
                                  primary_countries,primary_domains,affected_kpis,signature)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s) RETURNING id""",
            (
                topic.title,
                topic.summary or state.get("summary", ""),
                state.get("risk_score", 0),
                state.get("risk_level", "low"),
                topic.topic_key,
                topic.event_type,
                topic.uae_impact,
                self.entity_names(state, "countries"),
                json.dumps(state.get("risk_domains", [])),
                affected_kpis,
                  topic.topic_key,
            ),
        ).fetchone()[0]
        if topic.topic_id:
            connection.execute(
                """UPDATE topics
                   SET risk_score=GREATEST(risk_score,%s),
                       risk_level=%s,
                       summary=CASE WHEN length(summary) < length(%s) THEN %s ELSE summary END,
                       uae_impact=CASE WHEN length(uae_impact) < length(%s) THEN %s ELSE uae_impact END,
                       affected_kpis=(SELECT jsonb_agg(DISTINCT value)
                                      FROM jsonb_array_elements_text(affected_kpis || %s::jsonb) AS value),
                       updated_at=now()
                   WHERE id=%s""",
                (
                    state.get("risk_score", 0),
                    state.get("risk_level", "low"),
                    topic.summary,
                    topic.summary,
                    topic.uae_impact,
                    topic.uae_impact,
                    affected_kpis,
                    topic.topic_id,
                ),
            )
        connection.execute(
            """INSERT INTO topic_articles
               (topic_id,enriched_news_item_id,similarity_score,llm_match_confidence,is_primary_article)
               VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (topic_id, enriched_id, topic.similarity_score, topic.llm_match_confidence, topic.action == "create"),
        )

    def find_topic_by_key(self, topic_key: str) -> tuple[str, float] | None:
        if not topic_key:
            return None
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """SELECT id FROM topics
                   WHERE topic_key=%s OR signature=%s
                   ORDER BY updated_at DESC LIMIT 1""",
                (topic_key, topic_key),
              ).fetchone()
        return (str(row[0]), 0.95) if row else None
