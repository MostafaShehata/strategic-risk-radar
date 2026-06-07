from datetime import datetime, timezone

import httpx

from risk_radar.config import load_settings
from risk_radar.models import KeywordSpec, TimeWindow
from risk_radar.sources import GuardianSource


def test_guardian_fetches_keyword_group_and_strips_html():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert "api-key=test-key" in url
        assert "q=airspace+closure+OR+airport+closure" in url
        assert "from-date=2026-06-01" in url
        assert "to-date=2026-06-02" in url
        return httpx.Response(200, json={"response": {"results": [{
            "id": "world/one",
            "webTitle": "Fallback title",
            "webUrl": "https://www.theguardian.com/world/one",
            "webPublicationDate": "2026-06-02T09:30:00Z",
            "fields": {
                "headline": "Airport <b>closure</b> announced",
                "trailText": "Flights <i>suspended</i> after security incident.",
            },
        }]}})

    source = GuardianSource(
        {"id": "guardian", "url": "https://example.test/search", "api_key": "test-key", "retry_attempts": 1},
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    keyword = KeywordSpec("aviation disruption", ("airspace closure", "airport closure"))
    window = TimeWindow(
        datetime(2026, 6, 1, tzinfo=timezone.utc),
        datetime(2026, 6, 2, tzinfo=timezone.utc),
    )

    results = list(source.fetch((keyword,), window))

    assert results[0].keyword == "aviation disruption"
    assert results[0].retrieved_count == 1
    assert results[0].items[0].title == "Airport closure announced"
    assert results[0].items[0].summary == "Flights suspended after security incident."


def test_guardian_api_key_env_overrides_default(monkeypatch, tmp_path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
keywords:
  - name: test
    terms:
      - test
sources:
  - id: guardian
    type: guardian
    enabled: true
    url: https://content.guardianapis.com/search
    api_key_env: GUARDIAN_API_KEY
    api_key: test
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("GUARDIAN_API_KEY", "real-key")

    settings = load_settings(config)

    assert settings.sources[0]["api_key"] == "real-key"


def test_guardian_query_joins_terms_with_or():
    keyword = KeywordSpec("conflict", ("military escalation", "conflict escalation"))

    assert keyword.guardian_query == "military escalation OR conflict escalation"
