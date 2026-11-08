"""Tests for secret redaction (spec #45, #75, #96)."""

from app.core.redact import redact_exception, redact_secrets


def test_aviationstack_query_key_is_redacted():
    message = (
        "Client error '401 Unauthorized' for url "
        "'https://api.aviationstack.com/v1/flights?access_key=SECRET123&flight_iata=CA123'"
    )
    out = redact_secrets(message)
    assert "SECRET123" not in out
    assert "access_key=[REDACTED]" in out
    # Non-secret parts survive for debuggability.
    assert "CA123" in out
    assert "401" in out


def test_amap_key_query_param_is_redacted():
    message = (
        "Client error '401 Invalid key' for url "
        "'https://restapi.amap.com/v3/geocode/geo?address=beijing&key=AMAPKEY'"
    )
    out = redact_secrets(message)
    assert "AMAPKEY" not in out
    assert "key=[REDACTED]" in out
    assert "beijing" in out


def test_bearer_token_is_redacted():
    out = redact_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")
    assert "eyJhbGciOiJIUzI1NiJ9" not in out
    assert "Bearer [REDACTED]" in out


def test_api_key_header_is_redacted():
    out = redact_secrets("X-API-Key: my-raw-header-key")
    assert "my-raw-header-key" not in out
    assert "[REDACTED]" in out


def test_redact_exception_repr():
    class FakeError(Exception):
        pass

    exc = FakeError(
        "Client error '401' for url 'https://x/flights?access_key=TOPSECRET&iata=MU123'"
    )
    out = redact_exception(exc)
    assert "TOPSECRET" not in out
    assert "FakeError" in out
    assert "MU123" in out


def test_benign_text_is_unchanged():
    text = "FlightLookup: provider aerodatabox returned no result for CA123 on 2026-01-02"
    assert redact_secrets(text) == text
