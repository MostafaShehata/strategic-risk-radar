import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import UUID

from .config import Settings, load_settings
from .job_runner import RuntimeSettings, SourceJobRunner


def run_once(settings: Settings, database_url: str, runtime: RuntimeSettings) -> list[UUID]:
    with ThreadPoolExecutor(max_workers=max(1, len(settings.sources))) as executor:
        futures = [
            executor.submit(SourceJobRunner(settings, database_url, runtime).run, source_config)
            for source_config in settings.sources
        ]
        return [run_id for future in as_completed(futures) if (run_id := future.result())]


def run_scheduler(config_path: str, database_url: str, runtime: RuntimeSettings) -> None:
    settings = load_settings(config_path)
    if not settings.sources:
        raise ValueError("No enabled ingestion sources are configured")

    print(f"scheduler starting {len(settings.sources)} independent source runners", flush=True)
    with ThreadPoolExecutor(max_workers=len(settings.sources)) as executor:
        futures = [executor.submit(SourceScheduleWorker(settings, database_url, runtime, source).run) for source in settings.sources]
        for future in as_completed(futures):
            future.result()


class SourceScheduleWorker:
    def __init__(self, settings: Settings, database_url: str, runtime: RuntimeSettings, source_config: dict):
        self.settings = settings
        self.database_url = database_url
        self.runtime = runtime
        self.source_config = source_config

    def run(self) -> None:
        schedule_minutes = self._schedule_minutes()
        schedule_seconds = schedule_minutes * 60
        while True:
            started = time.monotonic()
            self._dispatch(schedule_minutes)
            sleep_seconds = max(0.0, schedule_seconds - (time.monotonic() - started))
            print(f"{self.source_id} runner sleeping for {sleep_seconds:.0f}s", flush=True)
            time.sleep(sleep_seconds)

    @property
    def source_id(self) -> str:
        return self.source_config["id"]

    def _schedule_minutes(self) -> float:
        schedule_minutes = float(self.source_config.get("schedule_minutes", self.runtime.interval_minutes))
        if schedule_minutes <= 0:
            raise ValueError(f"{self.source_id}: schedule_minutes must be greater than zero")
        return schedule_minutes

    def _dispatch(self, schedule_minutes: float) -> None:
        print(
            f"{self.source_id} runner dispatch: {datetime.now(timezone.utc).isoformat()} "
            f"(schedule={schedule_minutes}m, backfill_days={self.runtime.backfill_days}, "
            f"regular_window={self.runtime.regular_window_minutes}m)",
            flush=True,
        )
        try:
            SourceJobRunner(self.settings, self.database_url, self.runtime).run(self.source_config)
        except Exception as exc:
            print(f"{self.source_id} runner failed: {exc}", flush=True)
