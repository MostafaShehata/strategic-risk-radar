from datetime import datetime, timedelta, timezone

from risk_radar.storage import calculate_window


def test_missing_last_run_uses_configured_lookback():
    end = datetime.now(timezone.utc)
    window = calculate_window(end, None, 2)
    assert window.end - window.start == timedelta(hours=2)


def test_recent_last_run_resumes_from_last_end():
    end = datetime.now(timezone.utc)
    last_end = end - timedelta(minutes=30)
    window = calculate_window(end, last_end, 2)
    assert window.start == last_end


def test_stale_last_run_is_capped_to_configured_lookback():
    end = datetime.now(timezone.utc)
    window = calculate_window(end, end - timedelta(hours=6), 2)
    assert window.end - window.start == timedelta(hours=2)


def test_future_last_run_is_clamped_to_now():
    end = datetime.now(timezone.utc)
    window = calculate_window(end, end + timedelta(minutes=5), 2)
    assert window.start == end
