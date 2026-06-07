import argparse
import os

from .config import load_settings
from .job_runner import RuntimeSettings
from .scheduler import run_once, run_scheduler


def run(
    config_path: str,
    database_url: str,
    interval_minutes: float,
    backfill_days: float,
    regular_window_minutes: float,
) -> None:
    settings = load_settings(config_path)
    run_ids = run_once(settings, database_url, RuntimeSettings(
        interval_minutes=interval_minutes,
        backfill_days=backfill_days,
        regular_window_minutes=regular_window_minutes,
    ))
    print(f"ingestion cycle completed: {len(run_ids)} source jobs", flush=True)


def parse_runtime_settings() -> RuntimeSettings:
    runtime = RuntimeSettings(
        interval_minutes=float(os.getenv("INGESTION_INTERVAL_MINUTES", "10")),
        backfill_days=float(os.getenv("INGESTION_BACKFILL_DAYS", "7")),
        regular_window_minutes=float(
            os.getenv("INGESTION_REGULAR_WINDOW_MINUTES", os.getenv("INGESTION_INTERVAL_MINUTES", "10"))
        ),
    )
    validate_runtime_settings(runtime)
    return runtime


def validate_runtime_settings(runtime: RuntimeSettings) -> None:
    if runtime.interval_minutes <= 0:
        raise ValueError("INGESTION_INTERVAL_MINUTES must be greater than zero")
    if runtime.backfill_days <= 0:
        raise ValueError("INGESTION_BACKFILL_DAYS must be greater than zero")
    if runtime.regular_window_minutes <= 0:
        raise ValueError("INGESTION_REGULAR_WINDOW_MINUTES must be greater than zero")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sources.yaml")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    database_url = os.environ["DATABASE_URL"]
    runtime = parse_runtime_settings()
    if args.once:
        run(args.config, database_url, runtime.interval_minutes, runtime.backfill_days, runtime.regular_window_minutes)
    else:
        run_scheduler(args.config, database_url, runtime)


if __name__ == "__main__":
    main()
