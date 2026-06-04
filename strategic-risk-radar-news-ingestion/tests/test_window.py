from datetime import datetime, timedelta, timezone

from risk_radar.models import TimeWindow


def test_time_window_is_explicit():
    end = datetime.now(timezone.utc)
    window = TimeWindow(end - timedelta(hours=24), end)
    assert window.end - window.start == timedelta(hours=24)
