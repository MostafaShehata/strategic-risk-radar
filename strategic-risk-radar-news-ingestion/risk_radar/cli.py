import argparse
import os
import time
from datetime import datetime, timezone

import httpx

from .config import load_settings
from .sources import SourceSkipped, build_source
from .storage import Store


def run(
    config_path: str,
    database_url: str,
    interval_minutes: float,
    max_lookback_hours: float,
) -> None:
    settings = load_settings(config_path)
    store = Store(database_url)
    config_snapshot = {
        **settings.snapshot,
        "runtime": {
            "interval_minutes": interval_minutes,
            "max_lookback_hours": max_lookback_hours,
        },
    }
    run_id = store.create_run(config_snapshot)
    with httpx.Client(timeout=45, follow_redirects=True,
                      headers={"User-Agent": "Strategic-Risk-Radar-PoC/0.2"}) as client:
        for source_config in settings.sources:
            window = store.next_window(source_config["id"], max_lookback_hours)
            source_run_id = store.begin_source(
                run_id, source_config["id"], source_config["type"], window
            )
            started = time.monotonic()
            processed_keywords = set()
            warnings = []
            totals = {"requests": 0, "retrieved": 0, "matched": 0, "inserted": 0, "duplicates": 0}
            try:
                for result in build_source(source_config, client).fetch(settings.keywords, window):
                    inserted = sum(store.save_item(run_id, source_run_id, item) for item in result.items)
                    store.save_keyword_metric(source_run_id, result.keyword, result.request_count,
                                              result.retrieved_count, len(result.items), inserted)
                    totals["requests"] += result.request_count
                    if result.request_count:
                        totals["retrieved"] += result.retrieved_count
                    totals["matched"] += len(result.items)
                    totals["inserted"] += inserted
                    totals["duplicates"] += len(result.items) - inserted
                    processed_keywords.add(result.keyword)
                    if result.warning:
                        warnings.append(result.warning)
                store.finish_source(
                    source_run_id, "completed", totals,
                    int((time.monotonic() - started) * 1000),
                    "\n".join(warnings) or None,
                )
            except SourceSkipped as exc:
                for keyword in settings.keywords:
                    if keyword.name not in processed_keywords:
                        store.save_keyword_metric(source_run_id, keyword.name, 0, 0, 0, 0)
                store.finish_source(source_run_id, "skipped", totals,
                                    int((time.monotonic() - started) * 1000), str(exc))
                print(f"{source_config['id']}: skipped: {exc}", flush=True)
            except Exception as exc:
                for keyword in settings.keywords:
                    if keyword.name not in processed_keywords:
                        store.save_keyword_metric(source_run_id, keyword.name, 0, 0, 0, 0)
                store.finish_source(source_run_id, "error", totals,
                                    int((time.monotonic() - started) * 1000), str(exc))
                print(f"{source_config['id']}: {exc}")
    store.finish_run(run_id)
    print(f"ingestion run completed: {run_id}", flush=True)


def run_scheduler(
    config_path: str,
    database_url: str,
    interval_minutes: float,
    max_lookback_hours: float,
) -> None:
    interval_seconds = interval_minutes * 60
    while True:
        cycle_started = time.monotonic()
        print(
            f"scheduler cycle started: {datetime.now(timezone.utc).isoformat()} "
            f"(interval={interval_minutes}m, max_lookback={max_lookback_hours}h)",
            flush=True,
        )
        try:
            run(config_path, database_url, interval_minutes, max_lookback_hours)
        except Exception as exc:
            print(f"ingestion cycle failed: {exc}", flush=True)
        remaining = max(0, interval_seconds - (time.monotonic() - cycle_started))
        print(f"next cycle in {remaining:.0f} seconds", flush=True)
        time.sleep(remaining)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sources.yaml")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    database_url = os.environ["DATABASE_URL"]
    interval_minutes = float(os.getenv("INGESTION_INTERVAL_MINUTES", "30"))
    max_lookback_hours = float(os.getenv("INGESTION_MAX_LOOKBACK_HOURS", "24"))
    if interval_minutes <= 0:
        raise ValueError("INGESTION_INTERVAL_MINUTES must be greater than zero")
    if max_lookback_hours <= 0:
        raise ValueError("INGESTION_MAX_LOOKBACK_HOURS must be greater than zero")
    if args.once:
        run(args.config, database_url, interval_minutes, max_lookback_hours)
    else:
        run_scheduler(args.config, database_url, interval_minutes, max_lookback_hours)


if __name__ == "__main__":
    main()
