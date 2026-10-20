from app.core.timezones import normalize_timezone


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
