# Data Studio Backend

Read-only FastAPI service exposing ingestion runs, source execution windows,
source-type/status filters, keyword metrics, and documents to the Angular
frontend. `GET /api/runs/{id}` returns one source job with nested source and
keyword metrics for the run-centric UI.
