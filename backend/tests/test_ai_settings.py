from sqlalchemy import select

from app.core.crypto import decrypt_value
from app.models.ai_setting import UserAiSetting
from tests.conftest import auth_headers, register_and_login


def test_ai_settings_default(client):
    token = register_and_login(client, "ai_default")["access_token"]
    response = client.get("/api/v1/settings/ai", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert "api_key" not in body


def test_ai_settings_upsert_roundtrip(client, db):
    token = register_and_login(client, "ai_user")["access_token"]
    headers = auth_headers(token)

    response = client.put(
        "/api/v1/settings/ai",
        json={
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-secret-123",
            "temperature": 0.3,
            "context_limit": 8000,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "openai_compatible"
    assert body["model"] == "gpt-4o-mini"
    assert body["base_url"] == "https://api.example.com/v1"
    assert body["configured"] is True
    assert body["temperature"] == 0.3
    assert body["context_limit"] == 8000
    assert "api_key" not in body
    assert "sk-secret-123" not in response.text

    row = db.scalar(select(UserAiSetting))
    assert row is not None
    assert row.api_key_enc != "sk-secret-123"
    assert decrypt_value(row.api_key_enc) == "sk-secret-123"

    # Re-PUT without api_key keeps the existing key.
    response = client.put(
        "/api/v1/settings/ai",
        json={"provider": "openai", "model": "gpt-4o", "base_url": None},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "openai"
    db.refresh(row)
    assert decrypt_value(row.api_key_enc) == "sk-secret-123"


def test_ai_settings_delete(client):
    token = register_and_login(client, "ai_delete")["access_token"]
    headers = auth_headers(token)
    client.put(
        "/api/v1/settings/ai",
        json={"provider": "ollama", "model": "llama3", "api_key": "k"},
        headers=headers,
    )
    response = client.delete("/api/v1/settings/ai", headers=headers)
    assert response.status_code == 204
    assert client.get("/api/v1/settings/ai", headers=headers).json()["configured"] is False


def test_ai_settings_requires_auth(client):
    assert client.get("/api/v1/settings/ai").status_code == 401
    assert (
        client.put("/api/v1/settings/ai", json={"provider": "x", "model": "y"}).status_code == 401
    )
