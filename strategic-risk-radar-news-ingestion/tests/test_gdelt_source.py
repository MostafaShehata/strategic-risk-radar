from datetime import datetime, timedelta, timezone

import httpx

from risk_radar.models import TimeWindow
from risk_radar.sources import GdeltSource


def test_gdelt_keeps_only_english_articles():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "sourcelang%3Aenglish" in str(request.url)
        return httpx.Response(200, json={"articles": [
            {"url": "https://example.test/en", "title": "Border closure announced",
             "language": "English", "seendate": "20260604T120000Z"},
            {"url": "https://example.test/es", "title": "Cierre fronterizo",
             "language": "Spanish", "seendate": "20260604T120000Z"},
        ]})

    end = datetime.now(timezone.utc)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = GdeltSource(
            {"id": "gdelt", "url": "https://example.test", "retry_attempts": 1},
            client,
        )
        results = list(source.fetch(("border closure",), TimeWindow(end - timedelta(hours=1), end)))

    assert len(results[0].items) == 1
    assert results[0].items[0].title == "Border closure announced"


def test_gdelt_keyword_failure_does_not_stop_remaining_keywords():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadError("temporary failure")
        return httpx.Response(200, json={"articles": []})

    end = datetime.now(timezone.utc)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = GdeltSource(
            {"id": "gdelt", "url": "https://example.test", "retry_attempts": 1},
            client,
        )
        results = list(source.fetch(("first", "second"), TimeWindow(end - timedelta(hours=1), end)))

    assert [result.keyword for result in results] == ["first", "second"]
    assert attempts == 2
