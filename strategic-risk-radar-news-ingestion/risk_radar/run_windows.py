from datetime import datetime, timedelta

from .models import TimeWindow


def calculate_window(
    end: datetime,
    last_successful_end: datetime | None,
    backfill_days: float,
    regular_window_minutes: float,
) -> TimeWindow:
    regular_window = timedelta(minutes=regular_window_minutes)
    backfill_window = timedelta(days=1)
    if not last_successful_end:
        start = end - timedelta(days=backfill_days)
        return TimeWindow(start=start, end=min(start + backfill_window, end))
    last_successful_end = min(last_successful_end, end)
    regular_cutoff = end - regular_window
    if last_successful_end < regular_cutoff:
        daily_end = last_successful_end + backfill_window
        return TimeWindow(start=last_successful_end, end=daily_end if daily_end < regular_cutoff else end)
    return TimeWindow(start=max(end - regular_window, last_successful_end), end=end)
