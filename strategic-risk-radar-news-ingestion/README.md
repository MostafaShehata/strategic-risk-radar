# Strategic Risk Radar News Ingestion

Configuration-driven Python ingestion worker. It runs as a one-shot container,
records full execution metrics, and continues when one source fails.

GDELT is called once per keyword. `minimum_request_interval_seconds: 5.2`
enforces more than five seconds between requests from the single worker.

Each source run stores its requested `window_start` and `window_end`. The next
successful run resumes from the previous successful window end. Missing or
stale state is clamped to the most recent 24 hours.
