# Execution Trace

This trace follows one invocation of the ingestion container.

## 1. Container Startup

1. Docker Compose waits until the database health check succeeds.
2. The ingestion image starts with `ingest-news --config config/sources.yaml`.
3. The console entry point maps to `risk_radar.cli:main`.
4. `main()` reads `DATABASE_URL` and calls `run()`.

## 2. Configuration

1. `run()` calls `load_settings()` in `risk_radar/config.py`.
2. YAML keywords and enabled sources are loaded.
3. `RELIEFWEB_APPNAME` is resolved from the container environment.
4. The unchanged YAML structure is retained as the run's configuration
   snapshot for auditing.

## 3. Run Creation

1. `Store.create_run()` inserts one `ingestion_runs` row.
2. PostgreSQL generates the run UUID.
3. The run begins with status `running`.

## 4. Source Execution

For every configured source:

1. `Store.begin_source()` creates a `source_runs` row.
2. `build_source()` selects the GDELT, ReliefWeb, or RSS adapter.
3. The adapter returns one `KeywordResult` per configured keyword.
4. Every `KeywordResult` records request count, retrieved count, and matching
   raw items.

### GDELT

1. GDELT is queried separately for each keyword.
2. Before a request, `Source.request()` checks the previous request time.
3. It sleeps until at least `minimum_request_interval_seconds` has elapsed.
4. The configured value is `5.2`, exceeding GDELT's five-second limit.
5. HTTP 429 and transient server responses receive bounded retries.

### RSS

1. Each RSS feed is downloaded once.
2. The entries are checked locally against every keyword.
3. Only the first keyword metric records the network request; every keyword
   metric records how many feed entries were inspected and matched.

## 5. Document Persistence

For each matching document:

1. `Store.save_item()` attempts to insert the raw document.
2. `UNIQUE(source_id, external_id)` prevents exact source duplicates.
3. Existing documents are looked up instead of overwritten.
4. The document-keyword relationship is inserted.
5. A `run_item_observations` row records that this run observed the document.
6. `was_inserted` distinguishes new documents from duplicates.

## 6. Metrics Persistence

1. `Store.save_keyword_metric()` records per-source, per-keyword metrics.
2. `Store.finish_source()` records source totals, duration, status, and error.
3. A failing source is recorded as `error`; remaining sources continue.
4. `Store.finish_run()` aggregates all source rows into the parent run.

## 7. Browsing

1. Metabase connects directly to PostgreSQL on the Compose network.
2. `v_documents_browse` exposes readable document fields and keywords.
3. `v_run_summary` exposes high-level run outcomes.
4. Detailed dashboards can use `source_runs` and `keyword_run_metrics`.

