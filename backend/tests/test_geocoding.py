"""Address normalization and wrong-country rejection for the locate action."""

from app.providers.geocode import GeocodeResult
from app.services.geocoding import (
    address_query_variants,
    city_hint,
    country_hint,
    is_consistent,
)


def test_address_variants_strip_postcode_and_duplicates():
    assert address_query_variants("261 Outram Rd, Singapore, Singapore, 169057") == [
        "261 Outram Rd, Singapore, Singapore, 169057",
        "261 Outram Rd, Singapore",
    ]


def test_address_variants_keep_clean_addresses_unchanged():
    assert address_query_variants("10 Bayfront Ave, Singapore") == ["10 Bayfront Ave, Singapore"]
    assert address_query_variants("") == []


def test_country_hint_uses_last_non_postcode_component():
    assert country_hint("261 Outram Rd, Singapore, Singapore, 169057") == "singapore"
    assert country_hint("10 Bayfront Ave, Singapore") == "singapore"
    # Multi-word last component or CJK cannot be compared reliably.
    assert country_hint("1-1 Marunouchi, Chiyoda City") is None
    assert country_hint("北京市朝阳区建国门外大街1号") is None
    assert country_hint("") is None


def test_consistency_rejects_a_same_named_street_abroad():
    canada = GeocodeResult(lat=49.1445, lon=-103.3246, display_name="Outram, Saskatchewan, Canada")
    singapore = GeocodeResult(
        lat=1.2811, lon=103.8388, display_name="Outram Road, Singapore, Singapore"
    )
    assert is_consistent(canada, "singapore") is False
    assert is_consistent(singapore, "singapore") is True


def test_consistency_handles_country_aliases_and_localized_names():
    usa = GeocodeResult(lat=40.7, lon=-74.0, display_name="New York, United States")
    assert is_consistent(usa, "usa") is True
    # Localized display names cannot be verified; accept rather than reject.
    localized = GeocodeResult(lat=35.68, lon=139.69, display_name="東京都, 日本")
    assert is_consistent(localized, "tokyo") is True
    # No hint → no filtering.
    assert is_consistent(usa, None) is True


def test_city_hint_extracts_chinese_city():
    assert city_hint("北京市朝阳区建国门外大街1号") == "北京"
    assert city_hint("成都市武侯区天府大道北段1号") == "成都"
    assert city_hint("杭州市西湖区") == "杭州"
    # Municipality without the 市 suffix, leading the address.
    assert city_hint("北京朝阳区建国门外大街1号") == "北京"
    # A street named after another city must not hijack the hint.
    assert city_hint("广州市越秀区北京路") == "广州"
    # Latin addresses carry no CJK city hint.
    assert city_hint("261 Outram Rd, Singapore") is None
    assert city_hint("") is None


def test_consistency_rejects_wrong_chinese_city():
    beijing = GeocodeResult(lat=39.9, lon=116.4, display_name="北京市东城区王府井大街")
    shanghai = GeocodeResult(lat=31.2, lon=121.5, display_name="上海市黄浦区南京东路")
    assert is_consistent(beijing, "北京") is True
    assert is_consistent(shanghai, "北京") is False


def test_consistency_checks_chinese_city_romanization():
    latin = GeocodeResult(lat=39.9, lon=116.4, display_name="Beijing, China")
    wrong = GeocodeResult(lat=31.2, lon=121.5, display_name="Shanghai, China")
    assert is_consistent(latin, "北京") is True
    assert is_consistent(wrong, "北京") is False
    # Unknown city romanization or empty display cannot be verified — accept.
    assert is_consistent(latin, "廊坊") is True
    assert is_consistent(GeocodeResult(lat=39.9, lon=116.4), "北京") is True
