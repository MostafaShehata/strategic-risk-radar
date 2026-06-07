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
    body TEXT NOT NULL DEFAULT '',
    published_at TIMESTAMPTZ,
    raw_payload JSONB NOT NULL,
    first_seen_run_id UUID NOT NULL REFERENCES ingestion_runs(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processing_status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE (source_id, external_id)
);

ALTER TABLE raw_news_items ADD COLUMN IF NOT EXISTS body TEXT NOT NULL DEFAULT '';

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

CREATE TABLE IF NOT EXISTS article_content_fetches (
    id BIGSERIAL PRIMARY KEY,
    raw_news_item_id UUID NOT NULL REFERENCES raw_news_items(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    fetcher TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    language TEXT,
    published_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enrichment_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    processed_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    model_name TEXT NOT NULL DEFAULT '',
    error_message TEXT
);

ALTER TABLE raw_news_items ADD COLUMN IF NOT EXISTS enrichment_run_id UUID;
ALTER TABLE raw_news_items ADD COLUMN IF NOT EXISTS enrichment_claimed_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS raw_news_enrichment_claim_idx
ON raw_news_items(processing_status, enrichment_claimed_at);

CREATE TABLE IF NOT EXISTS enriched_news_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_news_item_id UUID NOT NULL UNIQUE REFERENCES raw_news_items(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    publication_date TIMESTAMPTZ,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'unknown',
    normalized_body TEXT NOT NULL DEFAULT '',
    body_source TEXT NOT NULL DEFAULT 'unknown',
    countries JSONB NOT NULL DEFAULT '[]'::jsonb,
    cities JSONB NOT NULL DEFAULT '[]'::jsonb,
    airports JSONB NOT NULL DEFAULT '[]'::jsonb,
    ports JSONB NOT NULL DEFAULT '[]'::jsonb,
    airlines JSONB NOT NULL DEFAULT '[]'::jsonb,
    companies JSONB NOT NULL DEFAULT '[]'::jsonb,
    organizations JSONB NOT NULL DEFAULT '[]'::jsonb,
    persons JSONB NOT NULL DEFAULT '[]'::jsonb,
    military_groups JSONB NOT NULL DEFAULT '[]'::jsonb,
    government_agencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_score INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'low',
    risk_domains JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_reason TEXT NOT NULL DEFAULT '',
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    enrichment_status TEXT NOT NULL DEFAULT 'pending',
    model_name TEXT NOT NULL DEFAULT '',
    trace JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS news_entities (
    id BIGSERIAL PRIMARY KEY,
    enriched_news_item_id UUID NOT NULL REFERENCES enriched_news_items(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    country_code TEXT NOT NULL DEFAULT '',
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS news_path_impacts (
    id BIGSERIAL PRIMARY KEY,
    enriched_news_item_id UUID NOT NULL REFERENCES enriched_news_items(id) ON DELETE CASCADE,
    origin TEXT NOT NULL DEFAULT '',
    destination TEXT NOT NULL DEFAULT '',
    path_code TEXT NOT NULL,
    impact_type TEXT NOT NULL,
    impact_level TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS news_kpi_impacts (
    id BIGSERIAL PRIMARY KEY,
    enriched_news_item_id UUID NOT NULL REFERENCES enriched_news_items(id) ON DELETE CASCADE,
    kpi_name TEXT NOT NULL,
    risk_score INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'low',
    impact_summary TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    risk_score INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'low',
    topic_key TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL DEFAULT '',
    uae_impact TEXT NOT NULL DEFAULT '',
    primary_countries JSONB NOT NULL DEFAULT '[]'::jsonb,
    primary_domains JSONB NOT NULL DEFAULT '[]'::jsonb,
    affected_kpis JSONB NOT NULL DEFAULT '[]'::jsonb,
    signature TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE topics ADD COLUMN IF NOT EXISTS topic_key TEXT NOT NULL DEFAULT '';
ALTER TABLE topics ADD COLUMN IF NOT EXISTS event_type TEXT NOT NULL DEFAULT '';
ALTER TABLE topics ADD COLUMN IF NOT EXISTS uae_impact TEXT NOT NULL DEFAULT '';
ALTER TABLE topics ADD COLUMN IF NOT EXISTS affected_kpis JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS topic_articles (
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    enriched_news_item_id UUID NOT NULL REFERENCES enriched_news_items(id) ON DELETE CASCADE,
    similarity_score NUMERIC(6,5) NOT NULL DEFAULT 0,
    llm_match_confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    is_primary_article BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (topic_id, enriched_news_item_id)
);

CREATE INDEX IF NOT EXISTS enriched_news_items_status_idx ON enriched_news_items(enrichment_status, created_at);
CREATE INDEX IF NOT EXISTS enriched_news_items_raw_idx ON enriched_news_items(raw_news_item_id);
CREATE INDEX IF NOT EXISTS news_entities_item_type_idx ON news_entities(enriched_news_item_id, entity_type);
CREATE INDEX IF NOT EXISTS news_path_impacts_item_idx ON news_path_impacts(enriched_news_item_id);
CREATE INDEX IF NOT EXISTS news_kpi_impacts_item_idx ON news_kpi_impacts(enriched_news_item_id);
CREATE INDEX IF NOT EXISTS news_kpi_impacts_kpi_idx ON news_kpi_impacts(kpi_name, risk_level);
CREATE INDEX IF NOT EXISTS topics_signature_idx ON topics(signature);
CREATE INDEX IF NOT EXISTS topics_topic_key_idx ON topics(topic_key);

CREATE OR REPLACE VIEW v_run_summary AS
SELECT r.*, count(s.id) AS source_count
FROM ingestion_runs r
LEFT JOIN source_runs s ON s.run_id = r.id
GROUP BY r.id;

DROP VIEW IF EXISTS v_documents_browse;
CREATE VIEW v_documents_browse AS
SELECT n.id, n.source_id, n.title, n.url, n.summary, n.body, n.published_at,
       n.first_seen_at, n.processing_status, n.enrichment_run_id, n.enrichment_claimed_at,
       string_agg(k.keyword, ', ' ORDER BY k.keyword) AS keywords
FROM raw_news_items n
LEFT JOIN raw_news_item_keywords k ON k.item_id = n.id
GROUP BY n.id;
