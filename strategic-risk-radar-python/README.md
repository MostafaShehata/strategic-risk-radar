# Strategic Risk Radar Python Ingestion

Configuration-driven Python ingestion worker. It runs as a one-shot container,
records full execution metrics, and continues when one source fails.

GDELT is called once per keyword. `minimum_request_interval_seconds: 5.2`
enforces more than five seconds between requests from the single worker.

