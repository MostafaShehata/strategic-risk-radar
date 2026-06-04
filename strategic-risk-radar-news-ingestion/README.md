# Strategic Risk Radar News Ingestion

Configuration-driven Python ingestion scheduler. It runs immediately on
startup, repeats every `INGESTION_INTERVAL_MINUTES` minutes, records full
execution metrics, and continues when one source fails.

GDELT is called once per keyword. `minimum_request_interval_seconds: 5.2`
enforces more than five seconds between requests from the single worker.

Each source run stores its requested `window_start` and `window_end`. The next
successful run resumes from the previous successful window end. Missing or
stale state is clamped to `INGESTION_MAX_LOOKBACK_HOURS`. Defaults are a
30-minute schedule and a 24-hour maximum lookback for source testing.

Use `ingest-news --once` to execute one cycle without starting the scheduler.
