# Data Studio Frontend

Custom Angular dashboard for browsing documents and viewing ingestion
operations. The run-centric screen lets users select one source job and see
its summary, source execution window, source errors, and per-keyword metrics.
The left menu filters jobs by source type and status, and the document browser
filters raw evidence by source and keyword. It is served by Nginx and proxies
`/api` to the backend.
