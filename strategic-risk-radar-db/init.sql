CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    total_retrieved INTEGER NOT NULL DEFAULT 0,
    total_matched INTEGER NOT NULL DEFAULT 0,
    total_inserted INTEGER NOT NULL DEFAULT 0,
    total_duplicates INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    config_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS source_runs (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    request_count INTEGER NOT NULL DEFAULT 0,
    retrieved_count INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    error_message TEXT
);

ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS window_start TIMESTAMPTZ;
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS window_end TIMESTAMPTZ;
UPDATE source_runs SET window_start = coalesce(window_start, started_at - interval '24 hours'),
                       window_end = coalesce(window_end, started_at)
WHERE window_start IS NULL OR window_end IS NULL;

CREATE TABLE IF NOT EXISTS keyword_run_metrics (
    source_run_id BIGINT NOT NULL REFERENCES source_runs(id),
    keyword TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    retrieved_count INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source_run_id, keyword)
);

CREATE TABLE IF NOT EXISTS raw_news_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    raw_payload JSONB NOT NULL,
    first_seen_run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS raw_news_item_keywords (
    item_id UUID NOT NULL REFERENCES raw_news_items(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    PRIMARY KEY (item_id, keyword)
);

CREATE TABLE IF NOT EXISTS run_item_observations (
    run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    source_run_id BIGINT NOT NULL REFERENCES source_runs(id),
    item_id UUID NOT NULL REFERENCES raw_news_items(id),
    keyword TEXT NOT NULL,
    was_inserted BOOLEAN NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_run_id, item_id, keyword)
);

CREATE INDEX IF NOT EXISTS source_runs_run_idx ON source_runs(run_id);
CREATE INDEX IF NOT EXISTS source_runs_latest_success_idx
ON source_runs(source_id, window_end DESC) WHERE status = 'completed';
CREATE INDEX IF NOT EXISTS raw_news_pending_idx ON raw_news_items(processing_status, first_seen_at);
CREATE INDEX IF NOT EXISTS observations_run_idx ON run_item_observations(run_id);

CREATE OR REPLACE VIEW v_run_summary AS
SELECT r.*, count(s.id) AS source_count
FROM ingestion_runs r
LEFT JOIN source_runs s ON s.run_id = r.id
GROUP BY r.id;

CREATE OR REPLACE VIEW v_documents_browse AS
SELECT n.id, n.source_id, n.title, n.url, n.summary, n.published_at,
       n.first_seen_at, n.processing_status,
       string_agg(k.keyword, ', ' ORDER BY k.keyword) AS keywords
FROM raw_news_items n
LEFT JOIN raw_news_item_keywords k ON k.item_id = n.id
GROUP BY n.id;
