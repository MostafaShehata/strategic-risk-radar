import httpx
from datetime import datetime, timedelta, timezone

from risk_radar.models import KeywordSpec, TimeWindow
from risk_radar.sources import GdeltSource


def test_gdelt_waits_between_keyword_requests(monkeypatch):
    sleeps = []
    times = iter([0.0, 0.0, 1.0, 6.0])
    monkeypatch.setattr("risk_radar.sources.time.monotonic", lambda: next(times))
    monkeypatch.setattr("risk_radar.sources.time.sleep", sleeps.append)

    def handler(request):
        return httpx.Response(200, json={"articles": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = GdeltSource({
            "id": "gdelt", "url": "https://example.test",
            "minimum_request_interval_seconds": 5.2, "retry_attempts": 1,
        }, client)
        end = datetime.now(timezone.utc)
        keywords = (KeywordSpec("first", ("first",)), KeywordSpec("second", ("second",)))
        list(source.fetch(keywords, TimeWindow(end - timedelta(hours=1), end)))

    assert sleeps == [5.2]


def test_gdelt_sleeps_one_minute_after_429(monkeypatch):
    sleeps = []
    monkeypatch.setattr("risk_radar.sources.time.monotonic", lambda: 0.0)
    monkeypatch.setattr("risk_radar.sources.time.sleep", sleeps.append)
    responses = iter([
        httpx.Response(429, json={"error": "too many requests"}),
        httpx.Response(200, json={"articles": []}),
    ])

    def handler(request):
        return next(responses)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = GdeltSource({
            "id": "gdelt", "url": "https://example.test", "retry_attempts": 2,
        }, client)
        end = datetime.now(timezone.utc)
        keyword = KeywordSpec("first", ("first",))
        list(source.fetch((keyword,), TimeWindow(end - timedelta(hours=1), end)))

    assert sleeps == [60]
