"""Hotel visibility to agents and the approval inbox (spec #17, #69, #85).

Covers: dashboard hotel count, JSON export of hotels, MCP read tools
(search_hotels / get_hotel), the MCP create_record(hotel) proposal that waits
for confirmation, duplicate-then-force, and the chat create_hotel proposal.
"""

import json

from app.providers.llm import LLMProvider, LLMResponse, LLMToolCall
from app.services import ai_agent as agent_mod
from tests.conftest import auth_headers, register_and_login

MCP_PATH = "/api/v1/mcp/"
INITIALIZE = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "pytest", "version": "1.0"},
}

HOTEL = {
    "hotel": "Marina Bay Sands",
    "check_in": "2026-04-29",
    "check_out": "2026-05-02",
    "room_type": "Deluxe King",
    "room_number": "1208",
    "address": "10 Bayfront Ave, Singapore",
    "price": "420.00",
    "currency": "SGD",
    "booking_reference": "MBS-778812",
}


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


def _rpc(client, token, method, params=None, *, req_id: int = 1):
    body: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    return client.post(MCP_PATH, json=body, headers=_headers(token))


def _open(client, token) -> None:
    resp = _rpc(client, token, "initialize", INITIALIZE)
    assert resp.status_code == 200, resp.text
    notified = client.post(
        MCP_PATH,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=_headers(token),
    )
    assert notified.status_code in (200, 202), notified.text


def _call(client, token, name, arguments):
    resp = _rpc(client, token, "tools/call", {"name": name, "arguments": arguments}, req_id=3)
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    return result.get("isError", False), json.loads(result["content"][0]["text"])


def _write_token(client, username: str) -> tuple[dict[str, str], str]:
    headers = auth_headers(register_and_login(client, username)["access_token"])
    created = client.post(
        "/api/v1/tokens", json={"name": f"{username}-mcp", "scope": "write"}, headers=headers
    ).json()
    return headers, created["token"]


def _propose_hotel(client, token, data=None) -> dict:
    payload = {"record_type": "hotel", "data": data or HOTEL}
    err, body = _call(client, token, "create_record", payload)
    assert not err, body
    return body


# -- dashboard / export --------------------------------------------------------


def test_dashboard_counts_hotels(client):
    headers = auth_headers(register_and_login(client, "hdash")["access_token"])
    client.post("/api/v1/hotels", json=HOTEL, headers=headers)
    body = client.get("/api/v1/dashboard", headers=headers).json()
    assert body["stats"]["hotels"] == 1
    stats = client.get("/api/v1/statistics", headers=headers).json()
    assert stats["totals"]["hotels"] == 1


def test_export_json_includes_hotels_and_hides_reference(client):
    headers = auth_headers(register_and_login(client, "hexport")["access_token"])
    client.post("/api/v1/hotels", json=HOTEL, headers=headers)
    bundle = client.get("/api/v1/export?format=json", headers=headers).json()
    assert len(bundle["hotels"]) == 1
    stay = bundle["hotels"][0]
    assert stay["hotel"] == "Marina Bay Sands"
    # Sensitive by default (spec #45): no confirmation number in a plain export.
    assert "booking_reference" not in stay

    with_sensitive = client.get(
        "/api/v1/export?format=json&include_sensitive=true", headers=headers
    ).json()
    assert with_sensitive["hotels"][0]["booking_reference"] == "MBS-778812"


# -- MCP read -----------------------------------------------------------------


def test_hotel_read_tools_exposed(client):
    headers, secret = _write_token(client, "hlist")
    _open(client, secret)
    resp = _rpc(client, secret, "tools/list", {}, req_id=2)
    names = {tool["name"] for tool in resp.json()["result"]["tools"]}
    assert {"search_hotels", "get_hotel"} <= names


def test_search_and_get_hotel_over_mcp(client):
    headers, secret = _write_token(client, "hget")
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()
    _open(client, secret)

    err, found = _call(client, secret, "search_hotels", {"query": "marina"})
    assert not err
    assert found["total"] == 1
    assert found["items"][0]["id"] == created["id"]
    # The confirmation number never leaves the tool layer (#45).
    assert "booking_reference" not in found["items"][0]

    err, one = _call(client, secret, "get_hotel", {"hotel_id": created["id"]})
    assert not err
    assert one["hotel"] == "Marina Bay Sands"
    assert one["nights"] == 3
    assert "booking_reference" not in one


def test_get_hotel_is_user_scoped(client):
    _, secret_a = _write_token(client, "hscope_a")
    headers_b = auth_headers(register_and_login(client, "hscope_b")["access_token"])
    created = client.post("/api/v1/hotels", json=HOTEL, headers=headers_b).json()
    _open(client, secret_a)
    err, body = _call(client, secret_a, "get_hotel", {"hotel_id": created["id"]})
    assert body["error"] == "hotel not found"


# -- MCP write (pending action) -----------------------------------------------


def test_create_hotel_proposal_waits_for_confirmation(client, db):
    headers, secret = _write_token(client, "hprop")
    proposal = _propose_hotel(client, secret)
    assert proposal["status"] == "pending_confirmation"
    action_id = proposal["pending_action_id"]

    # Nothing written yet (spec #69).
    assert client.get("/api/v1/hotels", headers=headers).json()["total"] == 0

    resp = client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "confirmed"

    stays = client.get("/api/v1/hotels", headers=headers).json()
    assert stays["total"] == 1
    assert stays["items"][0]["hotel"] == "Marina Bay Sands"


def test_duplicate_hotel_keeps_pending_then_force(client, db):
    headers, secret = _write_token(client, "hforce")
    # An existing stay with the same signature blocks confirmation.
    client.post("/api/v1/hotels", json=HOTEL, headers=headers)
    action_id = _propose_hotel(client, secret)["pending_action_id"]

    resp = client.post(f"/api/v1/pending-actions/{action_id}/confirm", json={}, headers=headers)
    assert resp.status_code == 409  # duplicate keeps the action pending
    stays = client.get("/api/v1/hotels", headers=headers).json()
    assert stays["total"] == 1

    forced = client.post(
        f"/api/v1/pending-actions/{action_id}/confirm", json={"force": True}, headers=headers
    )
    assert forced.status_code == 200
    assert forced.json()["status"] == "confirmed"
    assert client.get("/api/v1/hotels", headers=headers).json()["total"] == 2


# -- chat create_hotel proposal ------------------------------------------------


class _ScriptedProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def chat(self, *, messages, tools=None, temperature=None) -> LLMResponse:
        if self.calls >= len(self._responses):
            return LLMResponse(content="")
        self.calls += 1
        return self._responses[self.calls - 1]


def test_chat_create_hotel_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_hotel")["access_token"])
    client.put(
        "/api/v1/settings/ai",
        json={
            "provider": "openai_compatible",
            "model": "test-model",
            "base_url": "https://fake.example/v1",
            "api_key": "fake-key",
        },
        headers=headers,
    )

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="create_hotel",
                        arguments={"data": HOTEL},
                    )
                ],
            ),
            LLMResponse(content="I prepared a stay at Marina Bay Sands, please confirm."),
        ]
    )
    monkeypatch.setattr(agent_mod.AiAgentService, "_build_provider", lambda self, user_id: fake)

    resp = client.post(
        "/api/v1/ai/chat",
        json={"message": "add my Marina Bay Sands stay"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["proposals"]) == 1
    prop = body["proposals"][0]
    assert prop["action"] == "create_hotel"
    assert prop["record_type"] == "hotel"
    assert prop["data"]["hotel"] == "Marina Bay Sands"
    # Nothing was written without confirmation.
    assert client.get("/api/v1/hotels", headers=headers).json()["total"] == 0


TRIP = {
    "name": "东京之行",
    "start_date": "2026-04-29",
    "end_date": "2026-05-05",
    "origin": "上海",
    "destination": "东京",
    "status": "planned",
}


def test_chat_create_trip_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_trip")["access_token"])
    client.put(
        "/api/v1/settings/ai",
        json={
            "provider": "openai_compatible",
            "model": "test-model",
            "base_url": "https://fake.example/v1",
            "api_key": "fake-key",
        },
        headers=headers,
    )

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="create_trip",
                        arguments={"data": TRIP},
                    )
                ],
            ),
            LLMResponse(content="I prepared a Tokyo trip, please confirm."),
        ]
    )
    monkeypatch.setattr(agent_mod.AiAgentService, "_build_provider", lambda self, user_id: fake)

    resp = client.post(
        "/api/v1/ai/chat",
        json={"message": "帮我记一次东京之行"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["proposals"]) == 1
    prop = body["proposals"][0]
    assert prop["action"] == "create_trip"
    assert prop["record_type"] == "trip"
    assert prop["data"]["name"] == "东京之行"
    # Nothing was written without confirmation.
    assert client.get("/api/v1/trips", headers=headers).json()["total"] == 0


# -- chat update / delete proposals -------------------------------------------


FLIGHT = {
    "origin": "HKG",
    "destination": "SIN",
    "departure_time": "2026-09-26T01:45:00Z",
    "arrival_time": "2026-09-26T05:50:00Z",
    "carrier": "Cathay Pacific",
    "airline_code": "CX",
    "service_number": "CX659",
    "distance": "2540.0",
}


def _configure_chat_ai(client, headers) -> None:
    client.put(
        "/api/v1/settings/ai",
        json={
            "provider": "openai_compatible",
            "model": "test-model",
            "base_url": "https://fake.example/v1",
            "api_key": "fake-key",
        },
        headers=headers,
    )


def _chat_with_tool(client, headers, monkeypatch, name, arguments, message="go"):
    """Run one chat turn where the LLM calls ``name(arguments)``; return proposals."""
    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[LLMToolCall(id="call_1", name=name, arguments=arguments)],
            ),
            LLMResponse(content="Done, please confirm."),
        ]
    )
    monkeypatch.setattr(agent_mod.AiAgentService, "_build_provider", lambda self, user_id: fake)
    resp = client.post(
        "/api/v1/ai/chat",
        json={"message": message},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["proposals"]) == 1, body
    return body["proposals"][0]


def test_chat_update_trip_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_trip_upd")["access_token"])
    _configure_chat_ai(client, headers)
    trip = client.post("/api/v1/trips", json=TRIP, headers=headers).json()

    prop = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "update_trip",
        {"record_id": trip["id"], "data": {"name": "东京之行（改）"}},
        message="把行程名字改一下",
    )
    assert prop["action"] == "update_trip"
    assert prop["record_type"] == "trip"
    assert prop["data"]["record_id"] == trip["id"]
    assert prop["data"]["name"] == "东京之行（改）"
    # Only the changed field rides along — no full resend.
    assert set(prop["data"]) == {"record_id", "name"}
    # Nothing was written without confirmation.
    got = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert got["name"] == "东京之行"


def test_chat_delete_trip_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_trip_del")["access_token"])
    _configure_chat_ai(client, headers)
    trip = client.post("/api/v1/trips", json=TRIP, headers=headers).json()

    prop = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "delete_trip",
        {"record_id": trip["id"]},
        message="删掉这个行程",
    )
    assert prop["action"] == "delete_trip"
    assert prop["record_type"] == "trip"
    assert prop["data"] == {"record_id": trip["id"]}
    # Still exists until the user confirms.
    assert client.get(f"/api/v1/trips/{trip['id']}", headers=headers).status_code == 200


def test_chat_update_hotel_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_hotel_upd")["access_token"])
    _configure_chat_ai(client, headers)
    hotel = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()

    prop = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "update_hotel",
        {"record_id": hotel["id"], "data": {"room_number": "1500"}},
        message="把房号改成 1500",
    )
    assert prop["action"] == "update_hotel"
    assert prop["record_type"] == "hotel"
    assert prop["data"] == {"record_id": hotel["id"], "room_number": "1500"}
    # Nothing was written without confirmation.
    got = client.get(f"/api/v1/hotels/{hotel['id']}", headers=headers).json()
    assert got["room_number"] == "1208"


def test_chat_delete_hotel_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_hotel_del")["access_token"])
    _configure_chat_ai(client, headers)
    hotel = client.post("/api/v1/hotels", json=HOTEL, headers=headers).json()

    prop = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "delete_hotel",
        {"record_id": hotel["id"]},
        message="删掉这条酒店记录",
    )
    assert prop["action"] == "delete_hotel"
    assert prop["record_type"] == "hotel"
    assert prop["data"] == {"record_id": hotel["id"]}
    assert client.get(f"/api/v1/hotels/{hotel['id']}", headers=headers).status_code == 200


def test_chat_update_transport_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_flight_upd")["access_token"])
    _configure_chat_ai(client, headers)
    flight = client.post("/api/v1/flights", json=FLIGHT, headers=headers).json()

    prop = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "update_transport",
        {
            "record_type": "flight",
            "record_id": flight["id"],
            "data": {"departure_gate": "A12"},
        },
        message="把登机口改成 A12",
    )
    assert prop["action"] == "update_transport"
    assert prop["record_type"] == "flight"
    assert prop["data"] == {"record_id": flight["id"], "departure_gate": "A12"}
    # Nothing was written without confirmation.
    got = client.get(f"/api/v1/flights/{flight['id']}", headers=headers).json()
    assert got.get("departure_gate") in (None, "")


def test_chat_update_transport_proposal_normalizes_record_type(client, monkeypatch):
    """An unknown record_type from the LLM must collapse to "other" so the
    frontend dispatch (flight/train/other) can never land on the wrong endpoint.
    """
    from app.services.ai_tools import _update_transport_proposal

    for raw, expected in [
        ("plane", "other"),
        ("PLANE", "other"),
        ("", "other"),
        (None, "other"),
        ("flight", "flight"),
        ("train", "train"),
        ("other", "other"),
    ]:
        prop = _update_transport_proposal(
            {"record_type": raw, "record_id": "x", "data": {"seat": "1A"}}
        )
        assert prop.record_type == expected, f"input {raw!r} -> {prop.record_type!r}"


def test_update_transport_proposal_reanchors_wall_clock():
    """The web chat approval PATCHes straight to REST, bypassing the MCP gate,
    so the proposal builder itself must repair a wrong offset."""
    from app.services.ai_tools import _update_transport_proposal

    prop = _update_transport_proposal(
        {
            "record_type": "flight",
            "record_id": "x",
            "data": {
                "departure_time": "2026-05-01T10:05:00+00:00",
                "departure_timezone": "Asia/Shanghai",
            },
        }
    )
    assert prop.data["departure_time"] == "2026-05-01T02:05:00+00:00"
