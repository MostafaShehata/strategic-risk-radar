import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import psycopg

from .models import RawItem, TimeWindow


def calculate_window(
    end: datetime,
    last_successful_end: datetime | None,
    backfill_days: float,
    regular_window_minutes: float,
) -> TimeWindow:
    regular_window = timedelta(minutes=regular_window_minutes)
    backfill_window = timedelta(days=1)
    if not last_successful_end:
        start = end - timedelta(days=backfill_days)
        return TimeWindow(start=start, end=min(start + backfill_window, end))
    last_successful_end = min(last_successful_end, end)
    regular_cutoff = end - regular_window
    if last_successful_end < regular_cutoff:
        daily_end = last_successful_end + backfill_window
        return TimeWindow(start=last_successful_end, end=daily_end if daily_end < regular_cutoff else end)
    return TimeWindow(start=max(end - regular_window, last_successful_end), end=end)


class Store:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def create_run(self, config: dict[str, Any]) -> UUID:
        with psycopg.connect(self.database_url) as connection:
            return connection.execute(
                "INSERT INTO ingestion_runs(config_snapshot) VALUES (%s::jsonb) RETURNING id",
                (json.dumps(config),),
            ).fetchone()[0]

    def create_run_and_begin_source(
        self,
        config: dict[str, Any],
        source_id: str,
        source_type: str,
        window: TimeWindow,
        prevent_overlap: bool = False,
    ) -> tuple[UUID, int] | None:
        with psycopg.connect(self.database_url) as connection:
            if prevent_overlap:
                connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (source_id,))
                running = connection.execute(
                    "SELECT 1 FROM source_runs WHERE source_id=%s AND status='running' LIMIT 1",
                    (source_id,),
                ).fetchone()
                if running:
                    return None
            run_id = connection.execute(
                "INSERT INTO ingestion_runs(config_snapshot) VALUES (%s::jsonb) RETURNING id",
                (json.dumps(config),),
            ).fetchone()[0]
            source_run_id = connection.execute(
                """INSERT INTO source_runs(run_id, source_id, source_type, window_start, window_end)
                   VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (run_id, source_id, source_type, window.start, window.end),
            ).fetchone()[0]
            return run_id, source_run_id

    def next_window(
        self,
        source_id: str,
        backfill_days: float,
        regular_window_minutes: float,
        now: datetime | None = None,
    ) -> TimeWindow:
        end = now or datetime.now(timezone.utc)
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """SELECT max(window_end) FROM source_runs
                   WHERE source_id=%s AND status='completed' AND window_end IS NOT NULL""",
                (source_id,),
            ).fetchone()
        last_end = row[0] if row else None
        return calculate_window(end, last_end, backfill_days, regular_window_minutes)

    def begin_source(self, run_id: UUID, source_id: str, source_type: str, window: TimeWindow) -> int:
        with psycopg.connect(self.database_url) as connection:
            return connection.execute(
                """INSERT INTO source_runs(run_id, source_id, source_type, window_start, window_end)
                   VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (run_id, source_id, source_type, window.start, window.end),
            ).fetchone()[0]

    def save_item(self, run_id: UUID, source_run_id: int, item: RawItem) -> bool:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """INSERT INTO raw_news_items
                   (source_id,source_type,external_id,url,title,summary,body,published_at,raw_payload,first_seen_run_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                   ON CONFLICT(source_id,external_id) DO NOTHING RETURNING id""",
                (item.source_id, item.source_type, item.external_id, item.url, item.title,
                 item.summary, item.body, item.published_at, json.dumps(item.raw_payload, default=str), run_id),
            ).fetchone()
            inserted = row is not None
            item_id = row[0] if row else connection.execute(
                "SELECT id FROM raw_news_items WHERE source_id=%s AND external_id=%s",
                (item.source_id, item.external_id),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO raw_news_item_keywords(item_id,keyword) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (item_id, item.keyword),
            )
            connection.execute(
                """INSERT INTO run_item_observations(run_id,source_run_id,item_id,keyword,was_inserted)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (run_id, source_run_id, item_id, item.keyword, inserted),
            )
            return inserted

    def save_keyword_metric(self, source_run_id: int, keyword: str, request_count: int,
                            retrieved: int, matched: int, inserted: int) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """INSERT INTO keyword_run_metrics
                   (source_run_id,keyword,request_count,retrieved_count,matched_count,inserted_count,duplicate_count)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (source_run_id, keyword, request_count, retrieved, matched, inserted, matched - inserted),
            )

    def finish_source(self, source_run_id: int, status: str, totals: dict[str, int],
                      duration_ms: int, error: str | None = None) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """UPDATE source_runs SET completed_at=now(),status=%s,request_count=%s,
                   retrieved_count=%s,matched_count=%s,inserted_count=%s,duplicate_count=%s,
                   duration_ms=%s,error_message=%s WHERE id=%s""",
                (status, totals["requests"], totals["retrieved"], totals["matched"],
                 totals["inserted"], totals["duplicates"], duration_ms, error, source_run_id),
            )

    def finish_run(self, run_id: UUID) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """UPDATE ingestion_runs r SET completed_at=now(),
                   status=CASE WHEN x.errors=0 THEN 'completed' ELSE 'completed_with_errors' END,
                   total_retrieved=x.retrieved,total_matched=x.matched,total_inserted=x.inserted,
                   total_duplicates=x.duplicates,error_count=x.errors
                   FROM (SELECT run_id,coalesce(sum(retrieved_count),0) retrieved,
                         coalesce(sum(matched_count),0) matched,coalesce(sum(inserted_count),0) inserted,
                         coalesce(sum(duplicate_count),0) duplicates,
                         count(*) FILTER (WHERE status='error') errors
                         FROM source_runs WHERE run_id=%s GROUP BY run_id) x
                   WHERE r.id=x.run_id""",
                (run_id,),
            )
