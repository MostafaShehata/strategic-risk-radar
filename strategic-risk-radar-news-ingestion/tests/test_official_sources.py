from datetime import datetime, timezone

import httpx

from risk_radar.models import KeywordSpec, TimeWindow
from risk_radar.sources import (
    FaaAirportStatusSource,
    StateTravelAdvisoriesSource,
    WcoCustomsAnnouncementsSource,
    parse_faa_airport_status,
    parse_wco_newsroom,
)


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


def test_parse_wco_newsroom_extracts_customs_announcements():
    html = """
<li>
  <div class="dateFields"><p class="news-date date">01 June 2026</p></div>
  <h3><a href='/en/media/newsroom/2026/june/customs-update.aspx' class="headline">
    Global Trade Takes a Digital Leap with eATA Rollout in 30 Countries
  </a></h3>
</li>
"""

    news = parse_wco_newsroom(html, "https://www.wcoomd.org/en/media/newsroom.aspx")

    assert news[0]["title"] == "Global Trade Takes a Digital Leap with eATA Rollout in 30 Countries"
    assert news[0]["url"] == "https://www.wcoomd.org/en/media/newsroom/2026/june/customs-update.aspx"
    assert news[0]["published_at"] == datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_wco_source_matches_customs_keywords_from_detail_body():
    listing = """
<li>
  <div class="dateFields"><p class="news-date date">01 June 2026</p></div>
  <h3><a href='/en/media/newsroom/2026/june/customs-update.aspx' class="headline">
    Global Trade Takes a Digital Leap with eATA Rollout in 30 Countries
  </a></h3>
</li>
"""
    detail = '<div id="contentCol"><p>Customs modernization improves trade facilitation.</p></div><div id="footerWrapper">'

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/newsroom.aspx"):
            return httpx.Response(200, text=listing)
        return httpx.Response(200, text=detail)

    source = WcoCustomsAnnouncementsSource(
        {"id": "wco_customs_announcements", "url": "https://www.wcoomd.org/en/media/newsroom.aspx", "retry_attempts": 1},
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    keyword = KeywordSpec("customs and trade facilitation", ("customs modernization",))
    window = TimeWindow(
        datetime(2026, 6, 1, tzinfo=timezone.utc),
        datetime(2026, 6, 2, tzinfo=timezone.utc),
    )

    results = list(source.fetch((keyword,), window))

    assert results[0].retrieved_count == 1
    assert len(results[0].items) == 1
    assert results[0].items[0].source_type == "customs_announcement"
