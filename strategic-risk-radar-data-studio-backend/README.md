# Data Studio Backend

Read-only FastAPI service exposing ingestion runs, source execution windows,
keyword metrics, and documents to the Angular frontend. `GET /api/runs/{id}`
returns one run with nested sources and keyword metrics for the run-centric UI.
