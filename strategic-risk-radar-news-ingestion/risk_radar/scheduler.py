import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import UUID

from .config import Settings, load_settings
from .job_runner import RuntimeSettings, SourceJobRunner
from .repository import IngestionRepository


def run_once(settings: Settings, database_url: str, runtime: RuntimeSettings) -> list[UUID]:
    recover_abandoned_source_runs(database_url)
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
    recover_abandoned_source_runs(database_url)
    SourceScheduler(settings, database_url, runtime).run()


def recover_abandoned_source_runs(database_url: str) -> None:
    recovered = IngestionRepository(database_url).recover_running_source_runs(
        "Recovered after ingestion service startup; previous process stopped before closing the source run."
    )
    if recovered:
        print(f"recovered abandoned source runs count={recovered}", flush=True)


class SourceScheduler:
    def __init__(self, settings: Settings, database_url: str, runtime: RuntimeSettings):
        self.settings = settings
        self.database_url = database_url
        self.runtime = runtime
        self.next_due_at = {source["id"]: 0.0 for source in settings.sources}
        self.active: dict[str, Future[tuple[str, UUID | None]]] = {}

    def run(self) -> None:
        with ThreadPoolExecutor(max_workers=len(self.settings.sources)) as executor:
            while True:
                self._collect_finished()
                self._dispatch_due_sources(executor)
                time.sleep(self._heartbeat_seconds())

    def _collect_finished(self) -> None:
        for source_id, future in list(self.active.items()):
            if not future.done():
                continue
            try:
                completed_source_id, run_id = future.result()
                if run_id is None:
                    self.next_due_at[completed_source_id] = (
                        time.monotonic() + self._retry_delay_seconds(completed_source_id)
                    )
            except Exception as exc:
                print(f"{source_id} runner failed: {exc}", flush=True)
                self.next_due_at[source_id] = time.monotonic() + self._retry_delay_seconds(source_id)
            finally:
                self.active.pop(source_id, None)

    def _dispatch_due_sources(self, executor: ThreadPoolExecutor) -> None:
        now = time.monotonic()
        for source_config in self.settings.sources:
            source_id = source_config["id"]
            if source_id in self.active or now < self.next_due_at[source_id]:
                continue
            self.next_due_at[source_id] = now + self._schedule_seconds(source_config)
            self.active[source_id] = executor.submit(self._run_source_once, source_config)

    def _run_source_once(self, source_config: dict) -> tuple[str, UUID | None]:
        source_id = source_config["id"]
        schedule_minutes = self._schedule_minutes(source_config)
        print(
            f"{source_id} runner dispatch: {datetime.now(timezone.utc).isoformat()} "
            f"(schedule={schedule_minutes}m, backfill_days={self.runtime.backfill_days}, "
            f"regular_window={self.runtime.regular_window_minutes}m)",
            flush=True,
        )
        run_id = SourceJobRunner(self.settings, self.database_url, self.runtime).run(source_config)
        if run_id is not None:
            print(f"{source_id} next dispatch due in {self._schedule_seconds(source_config):.0f}s", flush=True)
        return source_id, run_id

    def _schedule_minutes(self, source_config: dict) -> float:
        source_id = source_config["id"]
        schedule_minutes = float(source_config.get("schedule_minutes", self.runtime.interval_minutes))
        if schedule_minutes <= 0:
            raise ValueError(f"{source_id}: schedule_minutes must be greater than zero")
        return schedule_minutes

    def _schedule_seconds(self, source_config: dict) -> float:
        return self._schedule_minutes(source_config) * 60

    def _heartbeat_seconds(self) -> float:
        return min(15.0, max(1.0, self.runtime.interval_minutes * 60 / 20))

    def _retry_delay_seconds(self, source_id: str) -> float:
        source = next(source for source in self.settings.sources if source["id"] == source_id)
        return min(60.0, self._schedule_seconds(source))
