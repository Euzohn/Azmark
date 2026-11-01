"""MCP endpoint (spec #85): auth, tool surface and user isolation."""

import json
from contextlib import nullcontext

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.core.security import hash_password
from app.main import app
from app.mcp import db as mcp_db
from app.models.user import User
from app.services.access_token import AccessTokenService
from tests.conftest import auth_headers, register_and_login

MCP_PATH = "/api/v1/mcp"

INITIALIZE = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "pytest", "version": "1.0"},
}

FLIGHT = {
    "origin": "HKG",
    "destination": "SIN",
    "departure_time": "2026-09-26T01:45:00Z",
    "arrival_time": "2026-09-26T05:50:00Z",
    "departure_timezone": "Asia/Hong_Kong",
    "arrival_timezone": "Asia/Singapore",
    "carrier": "Cathay Pacific",
    "service_number": "CX659",
}


def _headers(secret: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {secret}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


def _rpc(client, secret: str, method: str, params=None, *, req_id: int = 1):
    body: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    return client.post(MCP_PATH, json=body, headers=_headers(secret))


def _open_session(client, secret: str) -> None:
    response = _rpc(client, secret, "initialize", INITIALIZE)
    assert response.status_code == 200, response.text
    assert "result" in response.json(), response.text
    notified = client.post(
        MCP_PATH,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=_headers(secret),
    )
    assert notified.status_code in (200, 202), notified.text


def _tool_names(client, secret: str) -> set[str]:
    _open_session(client, secret)
    response = _rpc(client, secret, "tools/list", {}, req_id=2)
    assert response.status_code == 200, response.text
    return {tool["name"] for tool in response.json()["result"]["tools"]}


def _call(client, secret: str, name: str, arguments: dict | None = None):
    response = _rpc(
        client,
        secret,
        "tools/call",
        {"name": name, "arguments": arguments or {}},
        req_id=3,
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    return result.get("isError", False), json.loads(result["content"][0]["text"])


def _token(client, username: str, scope: str = "read") -> tuple[dict, str]:
    headers = auth_headers(register_and_login(client, username)["access_token"])
    created = client.post(
        "/api/v1/tokens",
        json={"name": f"{username}-mcp", "scope": scope},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return headers, created.json()["token"]


def test_missing_token_is_rejected(client):
    response = client.post(
        MCP_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


def test_session_jwt_is_not_accepted(client):
    headers = auth_headers(register_and_login(client, "mcp_jwt")["access_token"])
    response = client.post(
        MCP_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={**headers, "Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 401
    assert "personal access token" in response.json()["error"]


def test_unknown_and_revoked_tokens_are_rejected(client):
    headers, secret = _token(client, "mcp_revoke")

    bogus = client.post(
        MCP_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers=_headers("azm_not_a_real_token"),
    )
    assert bogus.status_code == 401

    listed = client.get("/api/v1/tokens", headers=headers).json()["items"]
    revoked = client.post(f"/api/v1/tokens/{listed[0]['id']}/revoke", headers=headers)
    assert revoked.status_code == 204

    response = _rpc(client, secret, "tools/list", {})
    assert response.status_code == 401


def test_only_read_tools_are_exposed(client):
    _, secret = _token(client, "mcp_tools")

    names = _tool_names(client, secret)
    assert names == {
        "search_records",
        "get_record",
        "list_trips",
        "get_trip",
        "get_statistics",
    }

    is_error, payload = _call(client, secret, "create_transport", {"record_type": "flight"})
    assert is_error is True
    assert "Unknown tool" in payload["error"]
    is_error, payload = _call(client, secret, "delete_transport", {"record_id": "x"})
    assert is_error is True


def test_search_records_is_user_scoped(client):
    headers_a, secret_a = _token(client, "mcp_owner_a")
    headers_b, secret_b = _token(client, "mcp_owner_b")

    flight_a = client.post("/api/v1/flights", json=FLIGHT, headers=headers_a)
    assert flight_a.status_code == 201, flight_a.text
    flight_b = client.post(
        "/api/v1/flights",
        json={**FLIGHT, "service_number": "SQ001", "carrier": "Singapore Airlines"},
        headers=headers_b,
    )
    assert flight_b.status_code == 201, flight_b.text

    is_error, payload = _call(client, secret_a, "search_records", {"query": ""})
    assert is_error is False
    assert payload["count"] == 1
    assert payload["items"][0]["service_number"] == "CX659"

    is_error, payload = _call(client, secret_a, "get_record", {"record_id": flight_b.json()["id"]})
    assert is_error is True
    assert payload["error"] == "record not found"

    is_error, payload = _call(client, secret_b, "search_records", {"query": ""})
    assert payload["items"][0]["service_number"] == "SQ001"


def test_trips_are_listed_and_readable(client):
    headers, secret = _token(client, "mcp_trip")

    trip = client.post(
        "/api/v1/trips",
        json={"name": "Autumn in Japan", "start_date": "2026-09-26"},
        headers=headers,
    )
    assert trip.status_code == 201, trip.text
    trip_id = trip.json()["id"]

    created = client.post("/api/v1/flights", json={**FLIGHT, "trip_id": trip_id}, headers=headers)
    assert created.status_code == 201, created.text

    is_error, payload = _call(client, secret, "list_trips")
    assert is_error is False
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Autumn in Japan"

    is_error, payload = _call(client, secret, "get_trip", {"trip_id": trip_id})
    assert is_error is False
    assert payload["name"] == "Autumn in Japan"
    assert len(payload["records"]) == 1
    assert payload["records"][0]["service_number"] == "CX659"
    assert "user_id" not in payload


def test_get_trip_hides_other_users_trips(client):
    headers_a, secret_a = _token(client, "mcp_trip_a")
    headers_b, _ = _token(client, "mcp_trip_b")

    trip_b = client.post("/api/v1/trips", json={"name": "Private"}, headers=headers_b)
    assert trip_b.status_code == 201, trip_b.text

    is_error, payload = _call(client, secret_a, "get_trip", {"trip_id": trip_b.json()["id"]})
    assert is_error is True
    assert payload["error"] == "trip not found"

    is_error, payload = _call(client, secret_a, "get_trip", {"trip_id": "not-a-uuid"})
    assert is_error is True
    assert payload["error"] == "invalid trip id"

    is_error, payload = _call(client, secret_a, "list_trips")
    assert payload["total"] == 0


def test_statistics_cover_own_records(client):
    headers, secret = _token(client, "mcp_stats")
    created = client.post("/api/v1/flights", json=FLIGHT, headers=headers)
    assert created.status_code == 201, created.text

    is_error, payload = _call(client, secret, "get_statistics")
    assert is_error is False
    assert payload["totals"]["flights"] == 1
    assert payload["totals"]["journeys"] == 1


# --- Official SDK client round trip -----------------------------------------
# The tests above speak raw JSON-RPC; this one proves a real MCP client (the
# same transport Claude/Cursor use) can initialize, list and call a tool.


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_official_client_round_trip(db, monkeypatch):
    monkeypatch.setattr(mcp_db, "session_scope", lambda: nullcontext(db))

    user = User(username="mcp_client", password_hash=hash_password("secret123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    _, secret = AccessTokenService(db).create(user_id=user.id, name="Cursor", scope="read")

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {secret}"},
        ) as http_client:
            async with streamable_http_client(
                "http://test/api/v1/mcp", http_client=http_client
            ) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    assert {tool.name for tool in listed.tools} == {
                        "search_records",
                        "get_record",
                        "list_trips",
                        "get_trip",
                        "get_statistics",
                    }
                    result = await session.call_tool("search_records", {"query": ""})
                    assert result.is_error is False
                    payload = json.loads(result.content[0].text)
                    assert payload["count"] == 0
