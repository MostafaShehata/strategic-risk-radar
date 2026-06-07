# Strategic Risk Radar News Ingestion

Configuration-driven Python ingestion scheduler. It starts one independent
runner per enabled source, runs each source immediately on startup, repeats by
that source's `schedule_minutes`, records full execution metrics, and continues
when another source fails or retries.

GDELT is called once per keyword group. `minimum_request_interval_seconds: 5.2`
enforces more than five seconds between requests from the GDELT runner. If
GDELT returns HTTP `429 Too Many Requests`, the worker sleeps for `60` seconds
and then retries.

The configured keywords are five high-signal operational groups. Each group
contains several precise phrases joined with `OR` for one GDELT request. RSS
feeds are downloaded once and matched locally against any phrase in each group.

- Conflict escalation
- Maritime and cargo disruption
- Aviation and passenger disruption
- Migration and residency pressure
- Identity and border crime

Broad single words such as `displacement` are avoided because they generate
large volumes of unrelated articles. Keyword performance should be reviewed
using retrieved, matched, inserted, and duplicate metrics in Data Studio.

Each source run stores its requested `window_start` and `window_end`. The next
successful run resumes from the previous successful window end. Missing or
stale state is clamped to `INGESTION_MAX_LOOKBACK_HOURS`. Defaults are a
30-minute per-source schedule and a 24-hour maximum lookback for source
testing. `INGESTION_INTERVAL_MINUTES` is used as a fallback when a source does
not define `schedule_minutes`.

Use `ingest-news --once` to execute every enabled source once in parallel
without starting the scheduler.

## Test GDELT With Postman

Import `postman/GDELT-English-News.postman_collection.json` into Postman.

- Send `Single Configurable Keyword` to test one keyword. Change the
  `keyword`, `lookbackHours`, or `maxrecords` collection variables as needed.
- Run the `Project Keyword Groups - Run With 60000 ms Delay` folder to test all
  five configured query groups.
- In the Postman Collection Runner, set the request delay to at least `60000`
  milliseconds if you want to mirror the application retry behavior after
  throttling. GDELT may return HTTP `429` when requests are sent too quickly.

The collection automatically calculates the latest UTC date range and verifies
that successful responses contain an `articles` array with English results.

## Test Guardian With Postman

Import `postman/Guardian-News.postman_collection.json` into Postman.

- The collection variable `apiKey` defaults to Guardian's public `test` key.
  Replace it with your free developer key when you have one.
- Send `Single Configurable Keyword` to test one keyword. Change the
  `keyword`, `lookbackHours`, or `pageSize` collection variables as needed.
- Run the `Project Keyword Groups` folder to test all five configured query
  groups against the same date window used by the application.

The collection automatically calculates `from-date` and `to-date`, requests
English results, and validates that Guardian returns a successful response.

## RSS Retrieval Notes

RSS sources are not queried per keyword. Each RSS feed is downloaded once per
source run, filtered by the source time window, then matched locally against
the phrases in each keyword group.

If a run shows `0` retrieved RSS entries, check the source run window first.
After an earlier successful run, the next window starts from the previous
window end. That can be only a few minutes, so a quiet feed may legitimately
produce no entries. If entries are retrieved but matched count is `0`, the feed
was available but none of the high-signal phrases appeared in the title or
summary.

## Guardian API Access

The second API source is Guardian Open Platform. It replaces ReliefWeb to avoid
approval delays during the PoC.

For quick development, the source uses Guardian's public `test` key by default.
For sustained use, register for a free developer key at
`https://open-platform.theguardian.com/access`, then set:

```env
GUARDIAN_API_KEY=your-guardian-developer-key
```

Restart the ingestion container after changing the key:

```powershell
docker compose up -d --force-recreate news-ingestion
```
