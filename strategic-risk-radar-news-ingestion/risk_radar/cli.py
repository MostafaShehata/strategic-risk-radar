import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import UUID

import httpx

from .config import load_settings
from .sources import SourceSkipped, build_source
from .storage import Store


def run(
    config_path: str,
    database_url: str,
    interval_minutes: float,
    backfill_days: float,
    regular_window_minutes: float,
) -> None:
    settings = load_settings(config_path)
    run_ids = run_sources(settings, database_url, interval_minutes, backfill_days, regular_window_minutes, settings.sources)
    print(f"ingestion cycle completed: {len(run_ids)} source jobs", flush=True)


def run_source_job(
    settings,
    database_url: str,
    interval_minutes: float,
    backfill_days: float,
    regular_window_minutes: float,
    source_config: dict,
) -> UUID:
    store = Store(database_url)
    config_snapshot = {
        "keywords": settings.snapshot.get("keywords", []),
        "sources": [source_config],
        "runtime": {
            "interval_minutes": interval_minutes,
            "source_schedule_minutes": float(source_config.get("schedule_minutes", interval_minutes)),
            "backfill_days": backfill_days,
            "regular_window_minutes": regular_window_minutes,
        },
    }
    run_id = store.create_run(config_snapshot)
    source_run_id = None
    try:
        with httpx.Client(timeout=45, follow_redirects=True,
                          headers={"User-Agent": "Strategic-Risk-Radar-PoC/0.2"}) as client:
            window = store.next_window(source_config["id"], backfill_days, regular_window_minutes)
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
                print(f"{source_config['id']}: {exc}", flush=True)
        store.finish_run(run_id)
    except Exception:
        store.finish_run(run_id)
        raise
    print(f"{source_config['id']} job completed: {run_id}", flush=True)
    return run_id


def run_sources(
    settings,
    database_url: str,
    interval_minutes: float,
    backfill_days: float,
    regular_window_minutes: float,
    sources: tuple[dict, ...],
) -> list[UUID]:
    run_ids = []
    with ThreadPoolExecutor(max_workers=max(1, len(sources))) as executor:
        futures = [
            executor.submit(run_source_job, settings, database_url, interval_minutes, backfill_days,
                            regular_window_minutes, source)
            for source in sources
        ]
        for future in as_completed(futures):
            run_ids.append(future.result())
    return run_ids


def run_scheduler(
    config_path: str,
    database_url: str,
    interval_minutes: float,
    backfill_days: float,
    regular_window_minutes: float,
) -> None:
    settings = load_settings(config_path)
    if not settings.sources:
        raise ValueError("No enabled ingestion sources are configured")

    def source_runner(source_config: dict) -> None:
        source_id = source_config["id"]
        schedule_minutes = float(source_config.get("schedule_minutes", interval_minutes))
        if schedule_minutes <= 0:
            raise ValueError(f"{source_id}: schedule_minutes must be greater than zero")
        schedule_seconds = schedule_minutes * 60
        while True:
            started = time.monotonic()
            print(
                f"{source_id} runner dispatch: {datetime.now(timezone.utc).isoformat()} "
                f"(schedule={schedule_minutes}m, backfill_days={backfill_days}, "
                f"regular_window={regular_window_minutes}m)",
                flush=True,
            )
            try:
                run_source_job(settings, database_url, interval_minutes, backfill_days, regular_window_minutes,
                               source_config)
            except Exception as exc:
                print(f"{source_id} runner failed: {exc}", flush=True)
            sleep_seconds = max(0.0, schedule_seconds - (time.monotonic() - started))
            print(f"{source_id} runner sleeping for {sleep_seconds:.0f}s", flush=True)
            time.sleep(sleep_seconds)

    print(
        f"scheduler starting {len(settings.sources)} independent source runners",
        flush=True,
    )
    while True:
        with ThreadPoolExecutor(max_workers=len(settings.sources)) as executor:
            futures = [
                executor.submit(source_runner, source)
                for source in settings.sources
            ]
            for future in as_completed(futures):
                future.result()
        print("scheduler workers stopped; restarting in 5s", flush=True)
        time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sources.yaml")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    database_url = os.environ["DATABASE_URL"]
    interval_minutes = float(os.getenv("INGESTION_INTERVAL_MINUTES", "10"))
    backfill_days = float(os.getenv("INGESTION_BACKFILL_DAYS", "7"))
    regular_window_minutes = float(os.getenv("INGESTION_REGULAR_WINDOW_MINUTES", str(interval_minutes)))
    if interval_minutes <= 0:
        raise ValueError("INGESTION_INTERVAL_MINUTES must be greater than zero")
    if backfill_days <= 0:
        raise ValueError("INGESTION_BACKFILL_DAYS must be greater than zero")
    if regular_window_minutes <= 0:
        raise ValueError("INGESTION_REGULAR_WINDOW_MINUTES must be greater than zero")
    if args.once:
        run(args.config, database_url, interval_minutes, backfill_days, regular_window_minutes)
    else:
        run_scheduler(args.config, database_url, interval_minutes, backfill_days, regular_window_minutes)


if __name__ == "__main__":
    main()
