import argparse
import os
import time

import httpx

from .config import load_settings
from .sources import build_source
from .storage import Store


def run(config_path: str, database_url: str) -> None:
    settings = load_settings(config_path)
    store = Store(database_url)
    run_id = store.create_run(settings.snapshot)
    with httpx.Client(timeout=45, follow_redirects=True,
                      headers={"User-Agent": "Strategic-Risk-Radar-PoC/0.2"}) as client:
        for source_config in settings.sources:
            window = store.next_window(source_config["id"])
            source_run_id = store.begin_source(
                run_id, source_config["id"], source_config["type"], window
            )
            started = time.monotonic()
            processed_keywords = set()
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
                store.finish_source(source_run_id, "completed", totals, int((time.monotonic() - started) * 1000))
            except Exception as exc:
                for keyword in settings.keywords:
                    if keyword not in processed_keywords:
                        store.save_keyword_metric(source_run_id, keyword, 0, 0, 0, 0)
                store.finish_source(source_run_id, "error", totals,
                                    int((time.monotonic() - started) * 1000), str(exc))
                print(f"{source_config['id']}: {exc}")
    store.finish_run(run_id)
    print(f"ingestion run completed: {run_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sources.yaml")
    args = parser.parse_args()
    run(args.config, os.environ["DATABASE_URL"])


if __name__ == "__main__":
    main()
