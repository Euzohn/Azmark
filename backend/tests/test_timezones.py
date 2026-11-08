from app.core.timezones import localize_transport_times, normalize_timezone


def test_none_and_blank_passthrough():
    assert normalize_timezone(None) is None
    assert normalize_timezone("") is None
    assert normalize_timezone("   ") is None


def test_iana_passthrough():
    assert normalize_timezone("Asia/Shanghai") == "Asia/Shanghai"
    assert normalize_timezone("UTC") == "UTC"
    assert normalize_timezone("America/New_York") == "America/New_York"


def test_curated_offsets_map_to_readable_zones():
    assert normalize_timezone("+00:00") == "UTC"
    assert normalize_timezone("+08:00") == "Asia/Shanghai"
    assert normalize_timezone("+09:00") == "Asia/Tokyo"
    assert normalize_timezone("+05:30") == "Asia/Kolkata"
    assert normalize_timezone("+07:00") == "Asia/Bangkok"
    assert normalize_timezone("-05:00") == "America/Bogota"
    assert normalize_timezone("-08:00") == "Pacific/Pitcairn"
    assert normalize_timezone("-10:00") == "Pacific/Honolulu"


def test_offset_without_colon():
    assert normalize_timezone("+0800") == "Asia/Shanghai"
    assert normalize_timezone("+8") == "Asia/Shanghai"
    assert normalize_timezone("-5") == "America/Bogota"


def test_uncurated_whole_hour_falls_back_to_etc_gmt():
    # IANA Etc/GMT signs are inverted: Etc/GMT-13 == UTC+13.
    assert normalize_timezone("+13:00") == "Etc/GMT-13"
    assert normalize_timezone("-11:00") == "Etc/GMT+11"


def test_non_whole_hour_without_curated_entry_is_kept():
    # +02:15 has no IANA representative and no Etc/GMT entry; keep the value
    # rather than silently dropping the user's data.
    assert normalize_timezone("+02:15") == "+02:15"


def test_unknown_value_returned_unchanged():
    assert normalize_timezone("GLM/nowhere") == "GLM/nowhere"


# -- re-anchoring transport times to their IANA zone --------------------------


def test_localize_reanchors_wall_clock_with_wrong_utc_offset():
    # Regression: the LLM writes 10:05 with +00:00 while the zone is +08:00.
    out = localize_transport_times(
        {"departure_time": "2026-05-01T10:05:00+00:00", "departure_timezone": "Asia/Shanghai"}
    )
    assert out["departure_time"] == "2026-05-01T02:05:00+00:00"


def test_localize_is_idempotent_for_correct_offsets():
    out = localize_transport_times(
        {"departure_time": "2026-05-01T10:05:00+08:00", "departure_timezone": "Asia/Shanghai"}
    )
    assert out["departure_time"] == "2026-05-01T02:05:00+00:00"


def test_localize_uses_departure_zone_for_actual_departure():
    out = localize_transport_times(
        {
            "actual_departure_time": "2026-05-01T10:20:00+00:00",
            "departure_timezone": "Asia/Shanghai",
            "actual_arrival_time": "2026-05-01T13:00:00+00:00",
            "arrival_timezone": "Asia/Tokyo",
        }
    )
    assert out["actual_departure_time"] == "2026-05-01T02:20:00+00:00"
    assert out["actual_arrival_time"] == "2026-05-01T04:00:00+00:00"


def test_localize_skips_date_only_and_missing_zone():
    out = localize_transport_times(
        {
            "departure_time": "2026-05-01",  # date only, no wall clock
            "arrival_time": "2026-05-01T10:05:00+00:00",  # no arrival_timezone
        }
    )
    assert out["departure_time"] == "2026-05-01"
    assert out["arrival_time"] == "2026-05-01T10:05:00+00:00"


def test_localize_ignores_invalid_zone_and_unparseable_value():
    out = localize_transport_times(
        {"departure_time": "2026-05-01T10:05:00+00:00", "departure_timezone": "GLM/nowhere"}
    )
    assert out["departure_time"] == "2026-05-01T10:05:00+00:00"

    out = localize_transport_times(
        {"departure_time": "not a time", "departure_timezone": "Asia/Shanghai"}
    )
    assert out["departure_time"] == "not a time"


def test_localize_accepts_offset_as_timezone_field():
    # The model sometimes fills the "timezone" with an offset; normalize first.
    out = localize_transport_times(
        {"departure_time": "2026-05-01T10:05:00+00:00", "departure_timezone": "+08:00"}
    )
    assert out["departure_time"] == "2026-05-01T02:05:00+00:00"


def test_localize_does_not_mutate_input():
    data = {
        "departure_time": "2026-05-01T10:05:00+00:00",
        "departure_timezone": "Asia/Shanghai",
    }
    localize_transport_times(data)
    assert data["departure_time"] == "2026-05-01T10:05:00+00:00"
