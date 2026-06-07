from datetime import datetime, timezone

from risk_radar.util import contains_keyword, stable_id
from risk_radar.util import parse_datetime


def test_keyword_matching_is_case_insensitive():
    assert contains_keyword("Possible BORDER CLOSURE", "border closure")


def test_keyword_matching_does_not_match_inside_words():
    assert not contains_keyword("Airport closure announced", "port closure")


def test_stable_id_is_repeatable():
    assert stable_id("a", "b") == stable_id("a", "b")


def test_parse_datetime_accepts_rss_date_only_values():
    assert parse_datetime("Thu, 04 Jun 2026") == datetime(2026, 6, 4, tzinfo=timezone.utc)
