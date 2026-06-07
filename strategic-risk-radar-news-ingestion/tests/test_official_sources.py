from datetime import datetime, timezone

import httpx

from risk_radar.models import KeywordSpec, TimeWindow
from risk_radar.sources import FaaAirportStatusSource, StateTravelAdvisoriesSource, parse_faa_airport_status


def test_state_travel_advisories_use_government_advisory_source_type():
    feed = b"""
<rss><channel><item>
  <title>Example - Level 4: Do Not Travel</title>
  <link>https://travel.example/advisory</link>
  <pubDate>Thu, 04 Jun 2026 00:00:00 GMT</pubDate>
  <description>Airspace closure and civil unrest reported.</description>
  <guid>travel-advisory-1</guid>
</item></channel></rss>
"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=feed)

    source = StateTravelAdvisoriesSource(
        {"id": "us_state_travel_advisories", "url": "https://example.test/feed.xml", "retry_attempts": 1},
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    keyword = KeywordSpec("aviation disruption", ("airspace closure",))
    window = TimeWindow(
        datetime(2026, 6, 4, tzinfo=timezone.utc),
        datetime(2026, 6, 5, tzinfo=timezone.utc),
    )

    results = list(source.fetch((keyword,), window))

    assert results[0].retrieved_count == 1
    assert results[0].items[0].source_type == "government_advisory"


def test_parse_faa_airport_status_extracts_airport_closures():
    xml = """
<AIRPORT_STATUS_INFORMATION><Delay_type>
  <Name>Airport Closures</Name>
  <Airport_Closure_List><Airport>
    <ARPT>LGA</ARPT>
    <Reason>Airport closure due to operational constraints</Reason>
    <Start>Jun 07 at 04:53 UTC.</Start>
    <Reopen>Jun 07 at 10:00 UTC.</Reopen>
  </Airport></Airport_Closure_List>
</Delay_type></AIRPORT_STATUS_INFORMATION>
"""

    notices = parse_faa_airport_status(xml, 2026)

    assert notices[0]["title"] == "Airport Closures: LGA"
    assert notices[0]["url"] == "https://nasstatus.faa.gov/"
    assert notices[0]["published_at"] == datetime(2026, 6, 7, 4, 53, tzinfo=timezone.utc)


def test_faa_source_matches_airport_closure_keywords():
    xml = """
<AIRPORT_STATUS_INFORMATION><Delay_type>
  <Name>Airport Closures</Name>
  <Airport_Closure_List><Airport>
    <ARPT>LGA</ARPT>
    <Reason>Airport closure due to operational constraints</Reason>
    <Start>Jun 07 at 04:53 UTC.</Start>
    <Reopen>Jun 07 at 10:00 UTC.</Reopen>
  </Airport></Airport_Closure_List>
</Delay_type></AIRPORT_STATUS_INFORMATION>
"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml)

    source = FaaAirportStatusSource(
        {"id": "faa_airport_status", "url": "https://nasstatus.faa.gov/api/airport-status-information", "retry_attempts": 1},
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    keyword = KeywordSpec("aviation and passenger disruption", ("airport closure",))
    window = TimeWindow(
        datetime(2026, 6, 7, tzinfo=timezone.utc),
        datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    results = list(source.fetch((keyword,), window))

    assert results[0].retrieved_count == 1
    assert len(results[0].items) == 1
    assert results[0].items[0].source_type == "aviation_notice"
