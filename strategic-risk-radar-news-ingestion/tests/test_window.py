from datetime import datetime, timedelta, timezone

from risk_radar.storage import calculate_window


def test_missing_last_run_uses_configured_lookback():
    end = datetime.now(timezone.utc)
    window = calculate_window(end, None, 7, 10)
    assert window.start == end - timedelta(days=7)
    assert window.end - window.start == timedelta(days=1)


def test_old_last_run_advances_one_day():
    end = datetime.now(timezone.utc)
    last_end = end - timedelta(days=6)
    window = calculate_window(end, last_end, 7, 10)
    assert window.start == last_end
    assert window.end == last_end + timedelta(days=1)


def test_caught_up_run_uses_regular_window():
    end = datetime.now(timezone.utc)
    window = calculate_window(end, end - timedelta(minutes=2), 7, 10)
    assert window.end == end
    assert window.start == end - timedelta(minutes=2)


def test_final_backfill_window_catches_up_to_now():
    end = datetime.now(timezone.utc)
    window = calculate_window(end, end - timedelta(minutes=70), 7, 10)
    assert window.end == end
    assert window.start == end - timedelta(minutes=70)


def test_run_after_catch_up_uses_last_10_minutes():
    end = datetime.now(timezone.utc)
    window = calculate_window(end, end - timedelta(minutes=10), 7, 10)
    assert window.end == end
    assert window.start == end - timedelta(minutes=10)


def test_future_last_run_is_clamped_to_now():
    end = datetime.now(timezone.utc)
    window = calculate_window(end, end + timedelta(minutes=5), 7, 10)
    assert window.start == end
