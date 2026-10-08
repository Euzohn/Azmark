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
