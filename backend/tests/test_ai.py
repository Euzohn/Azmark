"""Tests for the AI chat endpoint and agent tool loop (spec #31, #32, #93)."""

import json

from app.providers.llm import LLMProvider, LLMResponse, LLMToolCall
from app.services.ai_tools import TOOLS, ToolPermission
from tests.conftest import auth_headers, register_and_login


class _ScriptedProvider(LLMProvider):
    """Returns a scripted sequence of responses for deterministic tests."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.last_messages: list[dict] = []

    async def chat(self, *, messages, tools=None, temperature=None) -> LLMResponse:
        if self.calls >= len(self._responses):
            return LLMResponse(content="")
        self.last_messages = messages
        resp = self._responses[self.calls]
        self.calls += 1
        return resp


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


def _configure_ai(client, headers, provider="openai_compatible", model="test-model"):
    """Store AI settings with a fake key so the agent can resolve a provider."""
    client.put(
        "/api/v1/settings/ai",
        json={
            "provider": provider,
            "model": model,
            "base_url": "https://fake.example/v1",
            "api_key": "fake-key",
        },
        headers=headers,
    )


def test_chat_requires_auth(client):
    assert client.post("/api/v1/ai/chat", json={"message": "hi"}).status_code == 401


def test_chat_not_configured(client):
    token = register_and_login(client, "ai_noconfig")["access_token"]
    response = client.post(
        "/api/v1/ai/chat", json={"message": "hello"}, headers=auth_headers(token)
    )
    assert response.status_code == 400
    assert "not configured" in response.json()["detail"].lower()


def test_chat_with_scripted_text_reply(client, monkeypatch):
    token = register_and_login(client, "ai_text")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider([LLMResponse(content="Hello from the assistant")])
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post("/api/v1/ai/chat", json={"message": "hi"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Hello from the assistant"
    assert body["proposals"] == []


def test_chat_search_records_tool(client, monkeypatch):
    token = register_and_login(client, "ai_search")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    # Seed a flight
    client.post("/api/v1/flights", json=FLIGHT, headers=headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="search_records",
                        arguments={"query": "CX659"},
                    )
                ],
            ),
            LLMResponse(content="You have 1 CX659 flight: HKG → SIN."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "find my CX659 flights"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "1 CX659 flight" in body["reply"]
    assert body["proposals"] == []


def test_chat_statistics_tool(client, monkeypatch):
    token = register_and_login(client, "ai_stats")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)
    client.post("/api/v1/flights", json=FLIGHT, headers=headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[LLMToolCall(id="call_1", name="get_statistics", arguments={})],
            ),
            LLMResponse(content="You have 1 flight covering 2540 km."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post(
        "/api/v1/ai/chat", json={"message": "how many flights?"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert "1 flight" in body["reply"]


def test_chat_create_proposal(client, monkeypatch):
    token = register_and_login(client, "ai_create")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="create_transport",
                        arguments={
                            "record_type": "flight",
                            "data": {
                                "origin": "HKG",
                                "destination": "NRT",
                                "service_number": "CX548",
                                "departure_time": "2026-10-20T08:00:00Z",
                                "carrier": "Cathay Pacific",
                                "airline_code": "CX",
                            },
                        },
                    )
                ],
            ),
            LLMResponse(content="I prepared a flight HKG → NRT, please confirm."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "add a flight HKG to NRT on CX548"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["proposals"]) == 1
    prop = body["proposals"][0]
    assert prop["action"] == "create_transport"
    assert prop["record_type"] == "flight"
    assert prop["data"]["origin"] == "HKG"
    assert prop["data"]["destination"] == "NRT"
    # The record must NOT have been created (spec #69 — confirmation required)
    flights = client.get("/api/v1/flights", headers=headers).json()
    assert flights["total"] == 0


def test_chat_delete_proposal(client, monkeypatch):
    token = register_and_login(client, "ai_delete")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)
    created = client.post("/api/v1/flights", json=FLIGHT, headers=headers).json()

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="delete_transport",
                        arguments={
                            "record_type": "flight",
                            "record_id": created["id"],
                        },
                    )
                ],
            ),
            LLMResponse(content="I prepared deletion, please confirm."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": f"delete flight {created['id']}"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["proposals"]) == 1
    assert body["proposals"][0]["action"] == "delete_transport"
    # Must NOT have been deleted
    assert client.get(f"/api/v1/flights/{created['id']}", headers=headers).status_code == 200


def test_tool_permissions_classified():
    assert TOOLS["search_records"].permission == ToolPermission.READ
    assert TOOLS["get_statistics"].permission == ToolPermission.READ
    assert TOOLS["get_record"].permission == ToolPermission.READ
    assert TOOLS["lookup_flight"].permission == ToolPermission.READ
    assert TOOLS["create_transport"].permission == ToolPermission.WRITE
    assert TOOLS["delete_transport"].permission == ToolPermission.DESTRUCTIVE


def test_chat_lookup_flight_then_create(client, monkeypatch):
    """LLM calls lookup_flight first, then create_transport with enriched data."""
    token = register_and_login(client, "ai_lookup")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider(
        [
            # Step 1: LLM calls lookup_flight
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="lookup_flight",
                        arguments={"flight_number": "CX659", "date": "2026-09-26"},
                    )
                ],
            ),
            # Step 2: LLM gets lookup result, calls create_transport with enriched data
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_2",
                        name="create_transport",
                        arguments={
                            "record_type": "flight",
                            "data": {
                                "origin": "HKG",
                                "destination": "SIN",
                                "service_number": "CX659",
                                "departure_time": "2026-09-26T01:45:00Z",
                                "arrival_time": "2026-09-26T05:50:00Z",
                                "carrier": "Cathay Pacific",
                                "airline_code": "CX",
                            },
                        },
                    )
                ],
            ),
            # Step 3: LLM summarizes
            LLMResponse(content="I found CX659 (HKG → SIN) and prepared a record. Please confirm."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "add my CX659 flight on 2026-09-26"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["proposals"]) == 1
    prop = body["proposals"][0]
    assert prop["record_type"] == "flight"
    assert prop["data"]["origin"] == "HKG"
    assert prop["data"]["destination"] == "SIN"
    assert "confirm" in body["reply"].lower()


def test_lookup_flight_no_provider_key_returns_local(client, monkeypatch):
    """lookup_flight without a provider key returns source='local' with hint."""
    token = register_and_login(client, "ai_local")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="lookup_flight",
                        arguments={"flight_number": "CA1234"},
                    )
                ],
            ),
            LLMResponse(content="I couldn't look up CA1234. What's the origin and destination?"),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "add CA1234"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["proposals"] == []
    assert "origin" in body["reply"].lower() or "couldn" in body["reply"].lower()


def test_system_prompt_includes_timezone_for_zh_cn(client, monkeypatch):
    """LLM should receive the user's timezone in the system prompt so it can
    append the correct offset to datetime strings extracted from screenshots."""
    token = register_and_login(client, "ai_tz_zh")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider([LLMResponse(content="ok")])
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    client.post("/api/v1/ai/chat", json={"message": "hi"}, headers=headers)

    system_msg = fake.last_messages[0]
    assert system_msg["role"] == "system"
    assert "+08:00" in system_msg["content"]
    assert "TIMEZONE HANDLING" in system_msg["content"]


def test_system_prompt_includes_timezone_for_en_us(client, monkeypatch):
    """en-US users should receive -05:00 in the system prompt."""
    token = register_and_login(client, "ai_tz_en")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider([LLMResponse(content="ok")])
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    # Set locale to en-US
    client.patch("/api/v1/auth/me", json={"locale": "en-US"}, headers=headers)

    client.post("/api/v1/ai/chat", json={"message": "hi"}, headers=headers)

    system_msg = fake.last_messages[0]
    assert "-05:00" in system_msg["content"]


def test_system_prompt_includes_field_inference_rules(client, monkeypatch):
    """The prompt must teach the model to infer status, airline_code, train_type,
    currency, timezones, etc. instead of only filling the obvious fields."""
    token = register_and_login(client, "ai_infer_prompt")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider([LLMResponse(content="ok")])
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    client.post("/api/v1/ai/chat", json={"message": "hi"}, headers=headers)

    system = fake.last_messages[0]["content"]
    assert "FIELD INFERENCE" in system
    assert "Today's date is" in system
    # status inference from dates
    assert "completed" in system
    assert "scheduled" in system
    # flight number → airline_code / carrier
    assert "airline_code" in system
    # train number → train_type (leading letter)
    assert "train_type" in system
    assert "G=高铁" in system
    # timezone / distance / currency inference
    assert "departure_timezone" in system
    assert "distance" in system
    assert "currency" in system
    # today's date is injected (YYYY-MM-DD)
    import re

    assert re.search(r"\d{4}-\d{2}-\d{2}", system)


def test_local_today_uses_offset():
    from datetime import timedelta

    from app.services.ai_agent import _offset_to_timedelta, local_today

    assert _offset_to_timedelta("+08:00") == timedelta(hours=8)
    assert _offset_to_timedelta("-05:00") == timedelta(hours=-5)
    assert _offset_to_timedelta("garbage") == timedelta(0)

    value = local_today("+08:00")
    assert len(value) == 10
    assert value[4] == "-" and value[7] == "-"


def test_create_transport_proposal_preserves_all_inferred_fields(client, monkeypatch):
    """Field inference is only useful if the proposal keeps every field the LLM
    sends, including status, terminals, gates, aircraft, times and PNR."""
    token = register_and_login(client, "ai_infer_create")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    data = {
        "origin": "HKG",
        "destination": "NRT",
        "status": "completed",
        "service_number": "CX548",
        "airline_code": "CX",
        "carrier": "Cathay Pacific",
        "departure_time": "2026-10-20T08:00:00+08:00",
        "arrival_time": "2026-10-20T13:10:00+09:00",
        "departure_timezone": "Asia/Hong_Kong",
        "arrival_timezone": "Asia/Tokyo",
        "departure_terminal": "T1",
        "departure_gate": "A12",
        "arrival_terminal": "T2",
        "arrival_gate": "B7",
        "check_in_desk": "D",
        "baggage_belt": "22",
        "aircraft_model": "A350-900",
        "aircraft_reg": "B-LRA",
        "cabin_class": "business",
        "seat": "12A",
        "distance": 2896.0,
        "currency": "HKD",
        "price": 5000,
        "booking_reference": "ABC123",
        "ticket_number": "160-1234567890",
        "notes": "window seat",
    }

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="create_transport",
                        arguments={"record_type": "flight", "data": data},
                    )
                ],
            ),
            LLMResponse(content="Prepared, please confirm."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "I flew CX548 HKG to NRT last week"},
        headers=headers,
    )
    assert response.status_code == 200
    prop = response.json()["proposals"][0]
    for key, value in data.items():
        assert prop["data"][key] == value


def test_create_train_proposal_keeps_train_type(client, monkeypatch):
    """A train number like G1234 should keep the inferred train_type."""
    token = register_and_login(client, "ai_infer_train")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    from app.services import ai_agent as agent_mod

    data = {
        "origin": "北京南",
        "destination": "上海虹桥",
        "status": "completed",
        "service_number": "G1234",
        "train_type": "高铁",
        "carriage": "05",
        "seat_type": "二等座",
        "departure_time": "2026-10-01T09:00:00+08:00",
        "arrival_time": "2026-10-01T13:30:00+08:00",
    }

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="create_transport",
                        arguments={"record_type": "train", "data": data},
                    )
                ],
            ),
            LLMResponse(content="Prepared, please confirm."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "I took train G1234 from Beijing to Shanghai"},
        headers=headers,
    )
    assert response.status_code == 200
    prop = response.json()["proposals"][0]
    assert prop["record_type"] == "train"
    assert prop["data"]["train_type"] == "高铁"
    assert prop["data"]["carriage"] == "05"
    assert prop["data"]["seat_type"] == "二等座"


def test_lookup_flight_returns_all_fields_to_llm(client, monkeypatch):
    """The lookup tool must forward terminal/gate/aircraft/timezone/actual times
    so the LLM can copy them into the create proposal."""
    from datetime import UTC, datetime

    from app.schemas.flight_lookup import FlightLookupResponse
    from app.services import ai_agent as agent_mod
    from app.services.flight_enrichment import FlightEnrichmentService

    token = register_and_login(client, "ai_lookup_fields")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    full = FlightLookupResponse(
        flight_number="CX659",
        airline_code="CX",
        airline_name="Cathay Pacific",
        airline_name_zh="国泰航空",
        origin_iata="HKG",
        destination_iata="SIN",
        origin_name="Hong Kong International",
        destination_name="Singapore Changi",
        departure_time=datetime(2026, 9, 26, 1, 45, tzinfo=UTC),
        arrival_time=datetime(2026, 9, 26, 5, 50, tzinfo=UTC),
        actual_departure_time=datetime(2026, 9, 26, 1, 50, tzinfo=UTC),
        actual_arrival_time=datetime(2026, 9, 26, 5, 55, tzinfo=UTC),
        departure_terminal="T1",
        departure_gate="A12",
        arrival_terminal="T3",
        arrival_gate="B7",
        check_in_desk="D",
        baggage_belt="22",
        aircraft_model="A350-900",
        aircraft_reg="B-LRA",
        departure_timezone="Asia/Hong_Kong",
        arrival_timezone="Asia/Singapore",
        status="scheduled",
        distance=2540.0,
        source="aerodatabox",
    )

    async def fake_lookup(self, *, user_id, flight_number, date, provider=None):
        return full

    monkeypatch.setattr(FlightEnrichmentService, "lookup", fake_lookup)

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="lookup_flight",
                        arguments={"flight_number": "CX659", "date": "2026-09-26"},
                    )
                ],
            ),
            LLMResponse(content="Found CX659."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )

    client.post(
        "/api/v1/ai/chat",
        json={"message": "look up CX659 on 2026-09-26"},
        headers=headers,
    )

    tool_msgs = [m for m in fake.last_messages if m["role"] == "tool"]
    assert tool_msgs
    payload = json.loads(tool_msgs[0]["content"])
    assert payload["airline_name_zh"] == "国泰航空"
    assert payload["departure_terminal"] == "T1"
    assert payload["departure_gate"] == "A12"
    assert payload["arrival_terminal"] == "T3"
    assert payload["arrival_gate"] == "B7"
    assert payload["check_in_desk"] == "D"
    assert payload["baggage_belt"] == "22"
    assert payload["aircraft_model"] == "A350-900"
    assert payload["aircraft_reg"] == "B-LRA"
    assert payload["departure_timezone"] == "Asia/Hong_Kong"
    assert payload["arrival_timezone"] == "Asia/Singapore"
    assert payload["actual_departure_time"] is not None
    assert payload["actual_arrival_time"] is not None


def test_create_transport_schema_exposes_inference_fields():
    """The tool JSON schema must advertise the fields the model should fill."""
    props = TOOLS["create_transport"].parameters["properties"]["data"]["properties"]
    for field in (
        "status",
        "departure_timezone",
        "arrival_timezone",
        "departure_terminal",
        "departure_gate",
        "arrival_terminal",
        "arrival_gate",
        "check_in_desk",
        "baggage_belt",
        "aircraft_model",
        "aircraft_reg",
        "train_type",
        "carriage",
        "seat_type",
        "ticket_type",
        "booking_reference",
        "ticket_number",
        "distance",
        "currency",
    ):
        assert field in props, f"missing field in create_transport schema: {field}"


def _scripted_create(client, headers, monkeypatch, record_type, data):
    """Run one chat turn where the LLM proposes create_transport(data)."""
    from app.services import ai_agent as agent_mod

    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="create_transport",
                        arguments={"record_type": record_type, "data": data},
                    )
                ],
            ),
            LLMResponse(content="Prepared, please confirm."),
        ]
    )
    monkeypatch.setattr(
        agent_mod.AiAgentService,
        "_build_provider",
        lambda self, user_id: fake,
    )
    response = client.post("/api/v1/ai/chat", json={"message": "add this trip"}, headers=headers)
    assert response.status_code == 200
    return response.json()["proposals"][0]


def test_create_proposal_infers_status_completed_for_past_dates(client, monkeypatch):
    from datetime import UTC, datetime, timedelta

    token = register_and_login(client, "ai_status_past")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    past = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    prop = _scripted_create(
        client,
        headers,
        monkeypatch,
        "flight",
        {
            "origin": "HKG",
            "destination": "SIN",
            "service_number": "CX659",
            "arrival_time": past,
        },
    )
    assert prop["data"]["status"] == "completed"


def test_create_proposal_infers_status_scheduled_for_future_dates(client, monkeypatch):
    from datetime import UTC, datetime, timedelta

    token = register_and_login(client, "ai_status_future")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    future = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    prop = _scripted_create(
        client,
        headers,
        monkeypatch,
        "flight",
        {
            "origin": "HKG",
            "destination": "SIN",
            "service_number": "CX659",
            "arrival_time": future,
        },
    )
    assert prop["data"]["status"] == "scheduled"


def test_create_proposal_infers_airline_code_and_carrier(client, monkeypatch):
    token = register_and_login(client, "ai_airline")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    prop = _scripted_create(
        client,
        headers,
        monkeypatch,
        "flight",
        {"origin": "HKG", "destination": "NRT", "service_number": "CX548"},
    )
    assert prop["data"]["airline_code"] == "CX"
    assert prop["data"].get("carrier")


def test_create_proposal_infers_train_type(client, monkeypatch):
    token = register_and_login(client, "ai_train_type")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    prop = _scripted_create(
        client,
        headers,
        monkeypatch,
        "train",
        {"origin": "北京南", "destination": "上海虹桥", "service_number": "G1234"},
    )
    assert prop["data"]["train_type"] == "高铁"


def test_create_proposal_does_not_override_explicit_values(client, monkeypatch):
    token = register_and_login(client, "ai_no_override")["access_token"]
    headers = auth_headers(token)
    _configure_ai(client, headers)

    prop = _scripted_create(
        client,
        headers,
        monkeypatch,
        "train",
        {
            "origin": "北京南",
            "destination": "上海虹桥",
            "service_number": "G1234",
            "train_type": "复兴号",
            "status": "scheduled",
        },
    )
    assert prop["data"]["train_type"] == "复兴号"
    assert prop["data"]["status"] == "scheduled"
