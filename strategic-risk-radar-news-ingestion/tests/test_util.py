from risk_radar.util import contains_keyword, stable_id


def test_keyword_matching_is_case_insensitive():
    assert contains_keyword("Possible BORDER CLOSURE", "border closure")


def test_stable_id_is_repeatable():
    assert stable_id("a", "b") == stable_id("a", "b")

