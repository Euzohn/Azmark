"""AI travel journal context tool (spec #88, #32, #34, #45, #70)."""

import asyncio
import json

from sqlalchemy import select

from app.models.user import User
from app.providers.llm import LLMProvider, LLMResponse, LLMToolCall
from app.services import ai_agent as agent_mod
from app.services.ai_tools import (
    MCP_READ_TOOL_NAMES,
    TOOLS,
    ToolPermission,
    _generate_trip_summary,
)
from tests.conftest import auth_headers, register_and_login

HOTEL = {
    "hotel": "Marina Bay Sands",
    "check_in": "2026-04-29",
    "check_out": "2026-05-02",
    "address": "10 Bayfront Ave, Singapore",
    "price": "420.00",
    "currency": "SGD",
    "booking_reference": "MBS-778812",
}

NOTE = {"title": "Singapore packing list", "content": "Passport, adapters, sunscreen"}

EXPENSE = {
    "category": "food",
    "amount": "12.50",
    "currency": "CNY",
    "description": "Lunch at Maxwell Food Centre",
}

PLACE = {
    "type": "attraction",
    "country": "China",
    "city": "上海",
    "district": "黄浦",
    "name": "外滩",
    "localized_name": "The Bund",
    "lat": 31.2400,
    "lon": 121.4900,
    "timezone": "Asia/Shanghai",
}


def _headers(client, username: str) -> dict[str, str]:
    return auth_headers(register_and_login(client, username)["access_token"])


def _user_id(db, username: str):
    return db.scalar(select(User).where(User.username == username)).id


def _flight(**overrides) -> dict:
    payload = {
        "origin": "HKG",
        "destination": "SIN",
        "airline_code": "CX",
        "service_number": "CX659",
        "departure_time": "2026-09-26T01:45:00Z",
        "arrival_time": "2026-09-26T05:50:00Z",
        "distance": "2540.0",
    }
    payload.update(overrides)
    return payload


def _train(**overrides) -> dict:
    payload = {
        "origin": "上海虹桥",
        "destination": "北京南",
        "carrier": "中国铁路",
        "service_number": "G2",
        "departure_time": "2026-04-01T01:00:00Z",
        "arrival_time": "2026-04-01T06:00:00Z",
    }
    payload.update(overrides)
    return payload


def test_trip_scope_bundles_only_that_trip(client, db):
    headers = _headers(client, "journal_trip")
    trip = client.post("/api/v1/trips", json={"name": "Kyoto Spring"}, headers=headers).json()
    other = client.post("/api/v1/trips", json={"name": "Other"}, headers=headers).json()

    client.post("/api/v1/flights", json=_flight(trip_id=trip["id"]), headers=headers)
    client.post("/api/v1/trains", json=_train(trip_id=other["id"]), headers=headers)
    client.post("/api/v1/hotels", json={**HOTEL, "trip_id": trip["id"]}, headers=headers)
    client.post("/api/v1/notes", json={**NOTE, "trip_id": trip["id"]}, headers=headers)
    client.post("/api/v1/expenses", json={**EXPENSE, "trip_id": trip["id"]}, headers=headers)
    place = client.post("/api/v1/places", json=PLACE, headers=headers).json()
    client.post(
        "/api/v1/activities",
        json={
            "name": "外滩夜景",
            "type": "sightseeing",
            "place_id": place["id"],
            "trip_id": trip["id"],
            "start_at": "2026-04-02T12:00:00Z",
        },
        headers=headers,
    )

    bundle = asyncio.run(
        _generate_trip_summary(db, _user_id(db, "journal_trip"), {"trip_id": trip["id"]})
    )

    assert bundle["scope"] == {"type": "trip", "trip_id": trip["id"]}
    assert bundle["trip"]["name"] == "Kyoto Spring"
    # The train on the other trip must not leak into this bundle.
    assert [record["service_number"] for record in bundle["records"]] == ["CX659"]
    assert [hotel["hotel"] for hotel in bundle["hotels"]] == ["Marina Bay Sands"]
    assert [activity["name"] for activity in bundle["activities"]] == ["外滩夜景"]
    # The activity only stores place_id; the referenced place is resolved too.
    assert [place["name"] for place in bundle["places"]] == ["外滩"]
    assert [note["title"] for note in bundle["notes"]] == ["Singapore packing list"]
    assert bundle["totals"] == {
        "records": 1,
        "hotels": 1,
        "activities": 1,
        "places": 1,
        "notes": 1,
        "expenses": 1,
    }
    assert float(bundle["expense_summary"]["converted_total"]) == 12.50
    assert not any(bundle["truncated"].values())


def test_year_scope_uses_departure_timezone(client, db):
    headers = _headers(client, "journal_year")
    # Local New Year's Eve in New York is already 2026 in UTC: the departure
    # timezone must decide, matching the statistics/Wrapped attribution.
    client.post(
        "/api/v1/flights",
        json=_flight(
            service_number="UA001",
            departure_time="2025-12-31T23:30:00-05:00",
            arrival_time="2026-01-01T06:00:00-05:00",
            departure_timezone="America/New_York",
            arrival_timezone="America/New_York",
        ),
        headers=headers,
    )
    client.post(
        "/api/v1/flights",
        json=_flight(
            service_number="CX659",
            departure_time="2026-03-01T10:00:00Z",
            arrival_time="2026-03-01T14:00:00Z",
        ),
        headers=headers,
    )
    client.post("/api/v1/hotels", json=HOTEL, headers=headers)

    user_id = _user_id(db, "journal_year")
    year_2025 = asyncio.run(_generate_trip_summary(db, user_id, {"year": 2025}))
    year_2026 = asyncio.run(_generate_trip_summary(db, user_id, {"year": 2026}))

    assert year_2025["scope"] == {"type": "year", "year": 2025}
    assert [record["service_number"] for record in year_2025["records"]] == ["UA001"]
    assert year_2025["hotels"] == []
    assert [record["service_number"] for record in year_2026["records"]] == ["CX659"]
    assert [hotel["hotel"] for hotel in year_2026["hotels"]] == ["Marina Bay Sands"]


def test_year_scope_includes_notes_from_trips_in_that_year(client, db):
    headers = _headers(client, "journal_year_notes")
    trip = client.post(
        "/api/v1/trips",
        json={"name": "Iceland 2026", "start_date": "2026-06-01", "end_date": "2026-06-10"},
        headers=headers,
    ).json()
    client.post("/api/v1/notes", json={**NOTE, "trip_id": trip["id"]}, headers=headers)
    client.post("/api/v1/notes", json={"title": "Unsorted idea"}, headers=headers)

    bundle = asyncio.run(
        _generate_trip_summary(db, _user_id(db, "journal_year_notes"), {"year": 2026})
    )

    assert [note["title"] for note in bundle["notes"]] == ["Singapore packing list"]


def test_city_scope_matches_stations_airports_and_places(client, db):
    headers = _headers(client, "journal_city")
    trip = client.post("/api/v1/trips", json={"name": "Shanghai weekend"}, headers=headers).json()
    client.post("/api/v1/trains", json=_train(), headers=headers)
    client.post("/api/v1/flights", json=_flight(), headers=headers)
    place = client.post("/api/v1/places", json=PLACE, headers=headers).json()
    client.post(
        "/api/v1/activities",
        json={
            "name": "外滩夜景",
            "type": "sightseeing",
            "place_id": place["id"],
            "trip_id": trip["id"],
            "start_at": "2026-04-02T12:00:00Z",
        },
        headers=headers,
    )

    user_id = _user_id(db, "journal_city")
    shanghai = asyncio.run(_generate_trip_summary(db, user_id, {"city": "上海"}))
    hong_kong = asyncio.run(_generate_trip_summary(db, user_id, {"city": "Hong Kong"}))

    assert shanghai["scope"] == {"type": "city", "city": "上海"}
    assert [record["service_number"] for record in shanghai["records"]] == ["G2"]
    assert [place["name"] for place in shanghai["places"]] == ["外滩"]
    assert [activity["name"] for activity in shanghai["activities"]] == ["外滩夜景"]
    # Hotels and expenses carry no city identity and stay out of city scope.
    assert shanghai["hotels"] == []
    assert shanghai["expenses"] == []
    # English city names resolve through the same airport alias table.
    assert [record["service_number"] for record in hong_kong["records"]] == ["CX659"]


def test_scope_is_user_isolated(client, db):
    headers_a = _headers(client, "journal_owner")
    trip = client.post("/api/v1/trips", json={"name": "Private"}, headers=headers_a).json()

    _headers(client, "journal_intruder")
    bundle = asyncio.run(
        _generate_trip_summary(db, _user_id(db, "journal_intruder"), {"trip_id": trip["id"]})
    )

    assert bundle == {"error": "trip not found"}


def test_sensitive_fields_never_reach_the_context(client, db):
    headers = _headers(client, "journal_secret")
    client.post(
        "/api/v1/flights",
        json=_flight(booking_reference="PNR-SECRET-123"),
        headers=headers,
    )
    trip = client.post(
        "/api/v1/trips",
        json={"name": "Secret trip", "start_date": "2026-09-01", "end_date": "2026-09-30"},
        headers=headers,
    ).json()
    long_note = "x" * 1200
    client.post(
        "/api/v1/notes",
        json={"title": "Long note", "content": long_note, "trip_id": trip["id"]},
        headers=headers,
    )

    bundle = asyncio.run(_generate_trip_summary(db, _user_id(db, "journal_secret"), {"year": 2026}))
    dumped = json.dumps(bundle)

    assert "PNR-SECRET-123" not in dumped
    assert "booking_reference" not in dumped
    assert len(bundle["notes"][0]["content"]) == 601  # 600 chars + ellipsis
    assert bundle["notes"][0]["content"].endswith("…")


def test_invalid_scopes_are_rejected(client, db):
    _headers(client, "journal_args")
    user_id = _user_id(db, "journal_args")

    assert asyncio.run(_generate_trip_summary(db, user_id, {}))["error"].startswith(
        "provide exactly one"
    )
    assert asyncio.run(_generate_trip_summary(db, user_id, {"year": 2026, "city": "上海"}))[
        "error"
    ].startswith("provide exactly one")
    assert asyncio.run(_generate_trip_summary(db, user_id, {"trip_id": "nope"})) == {
        "error": "invalid trip id"
    }
    assert asyncio.run(_generate_trip_summary(db, user_id, {"year": "abc"})) == {
        "error": "year must be an integer"
    }
    assert asyncio.run(_generate_trip_summary(db, user_id, {"year": 1800})) == {
        "error": "year out of range"
    }


def test_tool_is_read_only_and_not_published_to_mcp():
    tool = TOOLS["generate_trip_summary"]
    assert tool.permission is ToolPermission.READ
    assert tool.read is not None
    # spec #85 lists the MCP tool set explicitly; the journal helper stays in
    # the chat agent only.
    assert "generate_trip_summary" not in MCP_READ_TOOL_NAMES


class _ScriptedProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.seen: list[list[dict]] = []

    async def chat(self, *, messages, tools=None, temperature=None) -> LLMResponse:
        self.seen.append(messages)
        if len(self.seen) > len(self._responses):
            return LLMResponse(content="")
        return self._responses[len(self.seen) - 1]


def test_chat_runs_the_tool_and_feeds_facts_back(client, monkeypatch):
    """A READ tool must execute immediately and its result reach the model."""
    headers = _headers(client, "journal_chat")
    trip = client.post("/api/v1/trips", json={"name": "Kyoto Spring"}, headers=headers).json()
    client.post("/api/v1/flights", json=_flight(trip_id=trip["id"]), headers=headers)
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
                        name="generate_trip_summary",
                        arguments={"trip_id": trip["id"]},
                    )
                ],
            ),
            LLMResponse(content="Here is your memoir."),
        ]
    )
    monkeypatch.setattr(agent_mod.AiAgentService, "_build_provider", lambda self, user_id: fake)

    resp = client.post("/api/v1/ai/chat", json={"message": "写回忆"}, headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reply"] == "Here is your memoir."
    assert body["proposals"] == []
    # The second LLM turn sees the tool result with the user's own facts.
    second_turn = json.dumps(fake.seen[1], ensure_ascii=False)
    assert "CX659" in second_turn
    assert "Kyoto Spring" in second_turn
