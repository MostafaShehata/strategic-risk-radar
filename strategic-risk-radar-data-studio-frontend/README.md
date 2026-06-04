# Data Studio Frontend

Custom Angular dashboard for browsing documents and viewing ingestion
operations. The run-centric screen lets users select one ingestion run and see
its summary, source execution windows, source errors, and per-source keyword
metrics together. It is served by Nginx and proxies `/api` to the backend.
