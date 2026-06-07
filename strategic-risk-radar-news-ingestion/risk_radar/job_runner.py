import time
from dataclasses import dataclass
from uuid import UUID

import httpx

from .config import Settings
from .models import KeywordResult, KeywordSpec
from .repository import IngestionRepository
from .source_clients import SourceSkipped, build_source


@dataclass(frozen=True)
class RuntimeSettings:
    interval_minutes: float
    backfill_days: float
    regular_window_minutes: float


@dataclass
class SourceRunTotals:
    requests: int = 0
    retrieved: int = 0
    matched: int = 0
    inserted: int = 0
    duplicates: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "requests": self.requests,
            "retrieved": self.retrieved,
            "matched": self.matched,
            "inserted": self.inserted,
            "duplicates": self.duplicates,
        }


class SourceJobRunner:
    def __init__(self, settings: Settings, database_url: str, runtime: RuntimeSettings):
        self.settings = settings
        self.repository = IngestionRepository(database_url)
        self.runtime = runtime

    def run(self, source_config: dict) -> UUID | None:
        source_id = source_config["id"]
        window = self.repository.next_window(
            source_id,
            self.runtime.backfill_days,
            self.runtime.regular_window_minutes,
        )
        started_run = self.repository.try_begin_source_run(
            self._config_snapshot(source_config),
            source_id,
            source_config["type"],
            window,
        )
        if started_run is None:
            print(f"{source_id} job skipped: previous source run is still running", flush=True)
            return None

        run_id, source_run_id = started_run
        try:
            self._execute_source(source_config, run_id, source_run_id, window)
        finally:
            self.repository.finish_run(run_id)
        print(f"{source_id} job completed: {run_id}", flush=True)
        return run_id

    def _execute_source(self, source_config: dict, run_id: UUID, source_run_id: int, window) -> None:
        started = time.monotonic()
        totals = SourceRunTotals()
        processed_keywords: set[str] = set()
        warnings: list[str] = []
        try:
            with httpx.Client(
                timeout=45,
                follow_redirects=True,
                headers={"User-Agent": "Strategic-Risk-Radar-PoC/0.2"},
            ) as client:
                source = build_source(source_config, client)
                for result in source.fetch(self.settings.keywords, window):
                    self._save_result(run_id, source_run_id, result, totals)
                    processed_keywords.add(result.keyword)
                    if result.warning:
                        warnings.append(result.warning)
            self._finish(source_run_id, "completed", totals, started, "\n".join(warnings) or None)
        except SourceSkipped as exc:
            self._finish_incomplete(source_run_id, processed_keywords, totals, started, "skipped", str(exc))
            print(f"{source_config['id']}: skipped: {exc}", flush=True)
        except Exception as exc:
            self._finish_incomplete(source_run_id, processed_keywords, totals, started, "error", str(exc))
            print(f"{source_config['id']}: {exc}", flush=True)

    def _save_result(
        self,
        run_id: UUID,
        source_run_id: int,
        result: KeywordResult,
        totals: SourceRunTotals,
    ) -> None:
        inserted = sum(self.repository.save_item(run_id, source_run_id, item) for item in result.items)
        matched = len(result.items)
        self.repository.save_keyword_metric(
            source_run_id,
            result.keyword,
            result.request_count,
            result.retrieved_count,
            matched,
            inserted,
        )
        totals.requests += result.request_count
        if result.request_count:
            totals.retrieved += result.retrieved_count
        totals.matched += matched
        totals.inserted += inserted
        totals.duplicates += matched - inserted

    def _finish_incomplete(
        self,
        source_run_id: int,
        processed_keywords: set[str],
        totals: SourceRunTotals,
        started: float,
        status: str,
        message: str,
    ) -> None:
        self._save_missing_keyword_metrics(source_run_id, processed_keywords)
        self._finish(source_run_id, status, totals, started, message)

    def _save_missing_keyword_metrics(self, source_run_id: int, processed_keywords: set[str]) -> None:
        for keyword in self.settings.keywords:
            if keyword.name not in processed_keywords:
                self.repository.save_keyword_metric(source_run_id, keyword.name, 0, 0, 0, 0)

    def _finish(
        self,
        source_run_id: int,
        status: str,
        totals: SourceRunTotals,
        started: float,
        message: str | None,
    ) -> None:
        duration_ms = int((time.monotonic() - started) * 1000)
        self.repository.finish_source(source_run_id, status, totals.as_dict(), duration_ms, message)

    def _config_snapshot(self, source_config: dict) -> dict:
        return {
            "keywords": self.settings.snapshot.get("keywords", []),
            "sources": [source_config],
            "runtime": {
                "interval_minutes": self.runtime.interval_minutes,
                "source_schedule_minutes": float(source_config.get("schedule_minutes", self.runtime.interval_minutes)),
                "backfill_days": self.runtime.backfill_days,
                "regular_window_minutes": self.runtime.regular_window_minutes,
            },
        }
