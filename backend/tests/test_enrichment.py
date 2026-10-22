import pytest
from sqlalchemy import select

from app.core.crypto import decrypt_value
from app.models.provider_setting import ProviderSetting
from app.providers.base import FlightLookupResult
from tests.conftest import auth_headers, register_and_login


class FakeProvider:
    name = "fake"

    def __init__(self, api_key, *, client=None):
        self.api_key = api_key

    async def lookup(self, flight_number, *, date):
        if not self.api_key:
            return None
        return FlightLookupResult(
            flight_number=flight_number,
            airline_code="CX",
            airline_name="Cathay Pacific",
            origin_iata="HKG",
            destination_iata="SIN",
            origin_name="Hong Kong International Airport",
            destination_name="Singapore Changi Airport",
            aircraft="Boeing 777-300ER",
            status="scheduled",
            provider="fake",
        )


class OtherProvider:
    name = "other"

    def __init__(self, api_key, *, client=None):
        self.api_key = api_key

    async def lookup(self, flight_number, *, date):
        if not self.api_key:
            return None
        return FlightLookupResult(
            flight_number=flight_number,
            airline_code="CX",
            airline_name="Cathay Pacific",
            origin_iata="HKG",
            destination_iata="SIN",
            origin_name="Hong Kong International Airport",
            destination_name="Singapore Changi Airport",
            arrival_time=None,
            aircraft="Airbus A350-900",
            status="landed",
            provider="other",
        )


class ChineseOnlyProvider:
    """Mirrors VariFlight for domestic carriers: Chinese name only."""

    name = "chinonly"

    def __init__(self, api_key, *, client=None):
        self.api_key = api_key

    async def lookup(self, flight_number, *, date):
        if not self.api_key:
            return None
        return FlightLookupResult(
            flight_number=flight_number,
            airline_code="Y8",
            airline_name=None,
            airline_name_zh="金鹏航空",
            provider="chinonly",
        )


class EmptyProvider:
    name = "empty"

    def __init__(self, api_key, *, client=None):
        self.api_key = api_key

    async def lookup(self, flight_number, *, date):
        if not self.api_key:
            return None
        return None


class FailingProvider:
    name = "failing"

    def __init__(self, api_key, *, client=None):
        self.api_key = api_key

    async def lookup(self, flight_number, *, date):
        raise ValueError("boom")


@pytest.fixture(autouse=True)
def _register_fake_provider(monkeypatch):
    import app.providers as providers

    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "fake", FakeProvider)


def _put_key(client, token, provider: str, api_key: str = "secret-key"):
    return client.put(
        f"/api/v1/settings/provider-keys/{provider}",
        json={"api_key": api_key},
        headers=auth_headers(token),
    )


def test_lookup_local_fallback(client):
    token = register_and_login(client, "lk_local")["access_token"]
    response = client.post(
        "/api/v1/flights/lookup",
        json={"flight_number": "CX659"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "local"
    assert body["airline_code"] == "CX"
    assert body["airline_name"] == "Cathay Pacific"
    assert body["origin_iata"] is None


def test_lookup_with_provider(client):
    token = register_and_login(client, "lk_provider")["access_token"]
    assert _put_key(client, token, "fake").status_code == 200
    response = client.post(
        "/api/v1/flights/lookup",
        json={"flight_number": "CX659", "provider": "fake"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "fake"
    assert body["origin_iata"] == "HKG"
    assert body["destination_iata"] == "SIN"
    assert body["aircraft"] == "Boeing 777-300ER"


def test_lookup_keeps_local_english_with_provider_chinese(client, monkeypatch):
    import app.providers as providers

    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "chinonly", ChineseOnlyProvider)
    token = register_and_login(client, "lk_zh_name")["access_token"]
    assert _put_key(client, token, "chinonly").status_code == 200

    response = client.post(
        "/api/v1/flights/lookup",
        json={"flight_number": "Y87525", "provider": "chinonly"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "chinonly"
    assert body["airline_code"] == "Y8"
    # en-US keeps the local English name; zh-CN gets the provider's Chinese one.
    assert body["airline_name"] == "Suparna Airlines"
    assert body["airline_name_zh"] == "金鹏航空"


def test_merge_keeps_curated_name_when_codes_agree():
    """VariFlight returns legal names; the curated short name should win."""
    from app.services import reference
    from app.services.flight_enrichment import _merge

    local = reference.lookup_flight_number("MU5101")
    remote = FlightLookupResult(
        flight_number="MU5101",
        airline_code="MU",
        airline_name_zh="中国东方航空股份有限公司",
        provider="variflight",
    )
    merged = _merge(local, remote)
    assert merged.airline_code == "MU"
    assert merged.airline_name_zh == "中国东方航空"
    assert merged.airline_name == "China Eastern Airlines"


def test_merge_drops_local_name_when_provider_corrects_the_code():
    """A corrected carrier must not keep the prefix-guessed airline names."""
    from app.services import reference
    from app.services.flight_enrichment import _merge

    local = reference.lookup_flight_number("MU5101")
    remote = FlightLookupResult(
        flight_number="MU5101",
        airline_code="XX",
        airline_name_zh="另一家航司",
        provider="variflight",
    )
    merged = _merge(local, remote)
    assert merged.airline_code == "XX"
    assert merged.airline_name_zh == "另一家航司"
    assert merged.airline_name is None


def test_lookup_uses_configured_provider_by_default(client):
    token = register_and_login(client, "lk_default")["access_token"]
    assert _put_key(client, token, "fake").status_code == 200
    response = client.post(
        "/api/v1/flights/lookup",
        json={"flight_number": "CX659"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["source"] == "fake"


def test_lookup_unknown_provider_404(client):
    token = register_and_login(client, "lk_unknown")["access_token"]
    response = client.post(
        "/api/v1/flights/lookup",
        json={"flight_number": "CX659", "provider": "nope"},
        headers=auth_headers(token),
    )
    assert response.status_code == 404


def test_lookup_provider_failure_falls_back_to_local(client, monkeypatch):
    import app.providers as providers

    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "failing", FailingProvider)
    token = register_and_login(client, "lk_fail")["access_token"]
    assert _put_key(client, token, "failing").status_code == 200
    response = client.post(
        "/api/v1/flights/lookup",
        json={"flight_number": "CX659"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "local"
    assert body["airline_code"] == "CX"


def test_key_stored_encrypted(client, db):
    token = register_and_login(client, "lk_crypt")["access_token"]
    assert _put_key(client, token, "fake", api_key="top-secret-key").status_code == 200
    row = db.scalar(
        select(ProviderSetting).where(
            ProviderSetting.provider == "fake",
        )
    )
    assert row is not None
    assert row.encrypted_value != "top-secret-key"
    assert decrypt_value(row.encrypted_value) == "top-secret-key"


def test_settings_requires_auth(client):
    assert client.get("/api/v1/settings/provider-keys").status_code == 401


def test_lookup_all_returns_each_provider(client, monkeypatch):
    import app.providers as providers

    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "fake", FakeProvider)
    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "other", OtherProvider)
    token = register_and_login(client, "lk_all1")["access_token"]
    headers = auth_headers(token)
    _put_key(client, token, "fake", api_key="k1")
    _put_key(client, token, "other", api_key="k2")

    response = client.post(
        "/api/v1/flights/lookup-all",
        json={"flight_number": "CX659"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["flight_number"] == "CX659"
    results = {item["provider"]: item["data"] for item in body["results"]}
    assert set(results) == {"fake", "other"}
    assert results["fake"]["source"] == "fake"
    assert results["fake"]["aircraft"] == "Boeing 777-300ER"
    assert results["other"]["source"] == "other"
    assert results["other"]["aircraft"] == "Airbus A350-900"
    assert results["other"]["status"] == "completed"


def test_lookup_all_skips_provider_without_key(client, monkeypatch):
    import app.providers as providers

    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "fake", FakeProvider)
    token = register_and_login(client, "lk_all2")["access_token"]
    headers = auth_headers(token)
    _put_key(client, token, "fake", api_key="k1")

    response = client.post(
        "/api/v1/flights/lookup-all",
        json={"flight_number": "CX659"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["provider"] == "fake"
    assert body["results"][0]["data"]["source"] == "fake"


def test_lookup_all_returns_null_for_empty_provider(client, monkeypatch):
    import app.providers as providers

    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "empty", EmptyProvider)
    token = register_and_login(client, "lk_all3")["access_token"]
    headers = auth_headers(token)
    _put_key(client, token, "empty", api_key="k1")

    response = client.post(
        "/api/v1/flights/lookup-all",
        json={"flight_number": "CX659"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["provider"] == "empty"
    assert body["results"][0]["data"] is None


def test_lookup_all_no_keys_returns_empty(client):
    token = register_and_login(client, "lk_all4")["access_token"]
    response = client.post(
        "/api/v1/flights/lookup-all",
        json={"flight_number": "CX659"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["flight_number"] == "CX659"
    assert body["results"] == []


def test_lookup_all_requires_auth(client):
    assert (
        client.post("/api/v1/flights/lookup-all", json={"flight_number": "CX659"}).status_code
        == 401
    )


def test_provider_keys_list_and_crud(client):
    token = register_and_login(client, "lk_settings")["access_token"]
    headers = auth_headers(token)

    response = client.get("/api/v1/settings/provider-keys", headers=headers)
    assert response.status_code == 200
    providers = response.json()["providers"]
    names = [item["provider"] for item in providers]
    assert "aerodatabox" in names
    assert all(item["configured"] is False for item in providers)

    response = _put_key(client, token, "aerodatabox", api_key="abc123")
    assert response.status_code == 200
    assert response.json() == {"provider": "aerodatabox", "configured": True}
    assert "abc123" not in response.text

    response = client.get("/api/v1/settings/provider-keys", headers=headers)
    statuses = {item["provider"]: item["configured"] for item in response.json()["providers"]}
    assert statuses["aerodatabox"] is True
    assert "abc123" not in response.text

    response = client.delete("/api/v1/settings/provider-keys/aerodatabox", headers=headers)
    assert response.status_code == 204
    response = client.get("/api/v1/settings/provider-keys", headers=headers)
    statuses = {item["provider"]: item["configured"] for item in response.json()["providers"]}
    assert statuses["aerodatabox"] is False


def test_unknown_provider_404(client):
    token = register_and_login(client, "lk_badprov")["access_token"]
    assert _put_key(client, token, "nope").status_code == 404
    assert (
        client.delete(
            "/api/v1/settings/provider-keys/nope", headers=auth_headers(token)
        ).status_code
        == 404
    )


def test_empty_api_key_rejected(client):
    token = register_and_login(client, "lk_emptykey")["access_token"]
    response = client.put(
        "/api/v1/settings/provider-keys/aerodatabox",
        json={"api_key": ""},
        headers=auth_headers(token),
    )
    assert response.status_code == 422


def test_merge_sources_prefers_confidence_and_fills_gaps():
    from app.services import reference
    from app.services.flight_enrichment import _merge_sources

    local = reference.lookup_flight_number("CX659")
    strong = FlightLookupResult(
        flight_number="CX659",
        airline_code="CX",
        origin_iata="HKG",
        status="scheduled",
        provider="aerodatabox",
    )
    weak = FlightLookupResult(
        flight_number="CX659",
        airline_code="CX",
        origin_iata="XXX",
        origin_name="Wrong Airport",
        destination_iata="SIN",
        destination_name="Singapore Changi Airport",
        arrival_gate="B7",
        status="completed",
        provider="variflight",
    )

    merged = _merge_sources(local, [("variflight", weak), ("aerodatabox", strong)])

    assert merged.source == "aerodatabox"
    assert merged.origin_iata == "HKG"  # the better source wins
    assert merged.origin_name is None  # name from a different airport is not borrowed
    assert merged.destination_iata == "SIN"  # gap filled by the weaker source
    assert merged.destination_name == "Singapore Changi Airport"
    assert merged.arrival_gate == "B7"
    assert merged.status == "scheduled"


def test_detect_conflicts_ignores_synonyms_and_small_time_skew():
    from datetime import UTC, datetime

    from app.services.flight_enrichment import _detect_conflicts

    a = FlightLookupResult(
        flight_number="CX659",
        origin_iata="HKG",
        departure_terminal="T1",
        departure_gate="A12",
        status="scheduled",
        departure_time=datetime(2026, 9, 26, 1, 45, tzinfo=UTC),
        provider="aerodatabox",
    )
    b = FlightLookupResult(
        flight_number="CX659",
        origin_iata="HKG",
        departure_terminal="1",
        departure_gate="A12",
        status="active",
        departure_time=datetime(2026, 9, 26, 1, 50, tzinfo=UTC),
        provider="variflight",
    )

    assert _detect_conflicts([("aerodatabox", a), ("variflight", b)]) == []


def test_detect_conflicts_reports_disagreements():
    from datetime import UTC, datetime

    from app.services.flight_enrichment import _detect_conflicts

    a = FlightLookupResult(
        flight_number="CX659",
        origin_iata="HKG",
        status="scheduled",
        departure_time=datetime(2026, 9, 26, 1, 45, tzinfo=UTC),
        provider="aerodatabox",
    )
    b = FlightLookupResult(
        flight_number="CX659",
        origin_iata="SIN",
        status="landed",
        departure_time=datetime(2026, 9, 26, 3, 0, tzinfo=UTC),
        provider="variflight",
    )

    conflicts = {
        item.field: item.values
        for item in _detect_conflicts([("aerodatabox", a), ("variflight", b)])
    }

    assert conflicts["origin_iata"] == {"aerodatabox": "HKG", "variflight": "SIN"}
    # Provider-specific status synonyms are normalised before comparison.
    assert conflicts["status"] == {"aerodatabox": "scheduled", "variflight": "completed"}
    assert "departure_time" in conflicts


def test_lookup_merged_cross_checks_all_configured_providers(client, db, monkeypatch):
    import asyncio
    from datetime import date

    from sqlalchemy import select

    import app.providers as providers
    from app.models.user import User
    from app.services.flight_enrichment import FlightEnrichmentService

    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "fake", FakeProvider)
    monkeypatch.setitem(providers.REGISTERED_PROVIDERS, "other", OtherProvider)
    token = register_and_login(client, "lk_merged")["access_token"]
    _put_key(client, token, "fake", api_key="k1")
    _put_key(client, token, "other", api_key="k2")

    user = db.scalar(select(User).where(User.username == "lk_merged"))
    assert user is not None
    merged = asyncio.run(
        FlightEnrichmentService(db).lookup_merged(
            user_id=user.id,
            flight_number="CX659",
            date=date(2026, 9, 26),
        )
    )

    assert merged.result.source == "fake"
    assert merged.result.origin_iata == "HKG"
    assert merged.result.aircraft == "Boeing 777-300ER"
    assert [item["provider"] for item in merged.sources] == ["fake", "other"]
    assert all(item["data"] is not None for item in merged.sources)
    conflicts = {item.field: item.values for item in merged.conflicts}
    assert conflicts["status"] == {"fake": "scheduled", "other": "completed"}
