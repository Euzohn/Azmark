"""Address normalization and wrong-country rejection for the locate action."""

from app.providers.geocode import GeocodeResult
from app.services.geocoding import address_query_variants, country_hint, is_consistent


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
