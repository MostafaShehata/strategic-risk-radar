# Strategic Risk Radar Data Studio

Metabase provides a free browser interface for inspecting the ingested data
and building run/source/keyword dashboards.

After deployment, open `http://localhost:3000` and add PostgreSQL:

- Host: `db`
- Port: `5432`
- Database: `risk_radar`
- Username: `risk_radar`
- Password: value from the root `.env`

Browse `v_documents_browse`, `v_run_summary`, `source_runs`, and
`keyword_run_metrics`.

