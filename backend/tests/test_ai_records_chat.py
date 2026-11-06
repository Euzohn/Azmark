"""AI chat proposals for expenses, notes, places and activities (spec #19, #21,
#14, #16, #18, #69).

These entity types follow the same rule as hotels/trips: the assistant never
writes directly — it builds an ``AiProposal`` the user must confirm. Each test
drives one chat turn with a scripted LLM that calls a tool, then asserts the
proposal shape and that nothing was persisted before confirmation.
"""

import json

from app.providers.llm import LLMProvider, LLMResponse, LLMToolCall
from app.services import ai_agent as agent_mod
from app.services.ai_tools import (
    _create_expense_proposal,
    _create_place_proposal,
    _update_activity_proposal,
)
from tests.conftest import auth_headers, register_and_login


class _ScriptedProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def chat(self, *, messages, tools=None, temperature=None) -> LLMResponse:
        if self.calls >= len(self._responses):
            return LLMResponse(content="")
        self.calls += 1
        return self._responses[self.calls - 1]


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
    """Run one chat turn where the LLM calls ``name(arguments)``; return the proposal."""
    fake = _ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[LLMToolCall(id="call_1", name=name, arguments=arguments)],
            ),
            LLMResponse(content="Please confirm."),
        ]
    )
    monkeypatch.setattr(agent_mod.AiAgentService, "_build_provider", lambda self, user_id: fake)
    resp = client.post("/api/v1/ai/chat", json={"message": message}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["proposals"]) == 1, body
    return body["proposals"][0]


def _create_trip(client, headers, name="Osaka 2026") -> dict:
    resp = client.post("/api/v1/trips", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# -- expenses -----------------------------------------------------------------


def test_create_expense_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_expense")["access_token"])
    _configure_chat_ai(client, headers)
    trip = _create_trip(client, headers)

    proposal = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "create_expense",
        {
            "data": {
                "amount": 18.5,
                "currency": "jpy",
                "category": "food",
                "occurred_at": "2026-04-02T12:00:00Z",
                "description": "Laksa dinner",
                "trip_id": trip["id"],
            }
        },
        message="记一笔 18.5 日元的拉面",
    )
    assert proposal["action"] == "create_expense"
    assert proposal["record_type"] == "expense"
    assert proposal["data"]["currency"] == "JPY"  # normalized to upper case
    assert proposal["data"]["category"] == "food"
    assert proposal["data"]["trip_id"] == trip["id"]
    # Nothing was written without confirmation.
    assert client.get("/api/v1/expenses", headers=headers).json()["total"] == 0

    # Confirming the proposal saves the expense (frontend dispatch path).
    created = client.post("/api/v1/expenses", json=proposal["data"], headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["currency"] == "JPY"


def test_create_expense_normalizes_bad_category(client):
    """An unknown enum from the LLM must collapse to a safe default, not 422 later."""
    proposal = _create_expense_proposal(
        {"data": {"amount": 5, "currency": "USD", "category": "LUNCH"}}
    )
    assert proposal.data["category"] == "other"
    assert proposal.data["currency"] == "USD"


# -- notes --------------------------------------------------------------------


def test_create_note_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_note")["access_token"])
    _configure_chat_ai(client, headers)
    trip = _create_trip(client, headers)

    proposal = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "create_note",
        {"data": {"title": "Osaka plan", "content": "Dotonbori crawl", "trip_id": trip["id"]}},
        message="记个笔记",
    )
    assert proposal["action"] == "create_note"
    assert proposal["record_type"] == "note"
    assert proposal["data"]["title"] == "Osaka plan"
    assert client.get("/api/v1/notes", headers=headers).json()["total"] == 0

    created = client.post("/api/v1/notes", json=proposal["data"], headers=headers)
    assert created.status_code == 201, created.text


def test_update_and_delete_note_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_note_upd")["access_token"])
    _configure_chat_ai(client, headers)
    note = client.post("/api/v1/notes", json={"title": "Old title"}, headers=headers).json()

    updated = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "update_note",
        {"record_id": note["id"], "data": {"title": "New title"}},
    )
    assert updated["action"] == "update_note"
    assert updated["data"] == {"record_id": note["id"], "title": "New title"}
    assert client.get(f"/api/v1/notes/{note['id']}", headers=headers).json()["title"] == "Old title"

    deleted = _chat_with_tool(
        client, headers, monkeypatch, "delete_note", {"record_id": note["id"]}
    )
    assert deleted["action"] == "delete_note"
    assert deleted["data"] == {"record_id": note["id"]}
    assert client.get(f"/api/v1/notes/{note['id']}", headers=headers).status_code == 200


# -- places -------------------------------------------------------------------


def test_create_place_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_place")["access_token"])
    _configure_chat_ai(client, headers)

    proposal = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "create_place",
        {
            "data": {
                "name": "Gardens by the Bay",
                "localized_name": "滨海湾花园",
                "type": "attraction",
                "city": "Singapore",
                "lat": 1.2816,
                "lon": 103.8636,
                "timezone": "Asia/Singapore",
            }
        },
        message="记一个地点",
    )
    assert proposal["action"] == "create_place"
    assert proposal["record_type"] == "place"
    assert proposal["data"]["name"] == "Gardens by the Bay"
    # A place has no trip membership of its own (spec #14).
    assert "trip_id" not in proposal["data"]
    assert client.get("/api/v1/places", headers=headers).json()["total"] == 0

    created = client.post("/api/v1/places", json=proposal["data"], headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["type"] == "attraction"


def test_create_place_normalizes_bad_type(client):
    proposal = _create_place_proposal({"data": {"name": "X", "type": "MALL"}})
    assert proposal.data["type"] == "place"


def test_add_place_to_trip_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_place_trip")["access_token"])
    _configure_chat_ai(client, headers)
    trip = _create_trip(client, headers)
    place = client.post(
        "/api/v1/places",
        json={"name": "Gardens by the Bay", "type": "attraction", "city": "Singapore"},
        headers=headers,
    ).json()

    proposal = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "add_place_to_trip",
        {
            "data": {
                "trip_id": trip["id"],
                "place_id": place["id"],
                "start_at": "2026-04-30T10:00:00Z",
            }
        },
        message="把地点加到行程",
    )
    assert proposal["action"] == "add_place_to_trip"
    assert proposal["record_type"] == "place"
    assert proposal["data"]["trip_id"] == trip["id"]
    assert proposal["data"]["place_id"] == place["id"]
    # The trip has no place item yet.
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert detail["items"] == []

    # Confirming adds the timeline item as a visit Activity (frontend dispatch path).
    added = client.post(
        f"/api/v1/trips/{trip['id']}/items",
        json={
            "item_type": "place",
            "item_id": place["id"],
            "start_at": proposal["data"]["start_at"],
        },
        headers=headers,
    )
    assert added.status_code == 201, added.text
    assert added.json()["item_type"] == "activity"
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    visit_items = [
        i
        for i in detail["items"]
        if i["item_type"] == "activity" and i["activity"]["type"] == "visit"
    ]
    assert len(visit_items) == 1


# -- activities ---------------------------------------------------------------


def test_create_activity_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_activity")["access_token"])
    _configure_chat_ai(client, headers)
    trip = _create_trip(client, headers)
    place = client.post(
        "/api/v1/places",
        json={"name": "Gardens by the Bay", "type": "attraction", "city": "Singapore"},
        headers=headers,
    ).json()

    proposal = _chat_with_tool(
        client,
        headers,
        monkeypatch,
        "create_activity",
        {
            "data": {
                "name": "Light show",
                "type": "sightseeing",
                "place_id": place["id"],
                "trip_id": trip["id"],
                "start_at": "2026-04-30T19:00:00Z",
                "end_at": "2026-04-30T20:00:00Z",
                "price": 18,
                "currency": "sgd",
            }
        },
        message="记一个活动",
    )
    assert proposal["action"] == "create_activity"
    assert proposal["record_type"] == "activity"
    assert proposal["data"]["currency"] == "SGD"
    assert proposal["data"]["place_id"] == place["id"]
    assert proposal["data"]["trip_id"] == trip["id"]
    assert client.get("/api/v1/activities", headers=headers).json()["total"] == 0

    created = client.post("/api/v1/activities", json=proposal["data"], headers=headers)
    assert created.status_code == 201, created.text
    # The activity mirrors into the trip timeline at its start_at.
    detail = client.get(f"/api/v1/trips/{trip['id']}", headers=headers).json()
    assert [i["item_type"] for i in detail["items"]] == ["activity"]


def test_update_activity_normalizes_type_and_currency(client):
    proposal = _update_activity_proposal(
        {
            "record_id": "abc",
            "data": {"type": "FOOD", "currency": "usd", "price": 9},
        }
    )
    assert proposal.action == "update_activity"
    assert proposal.data["type"] == "other"  # unknown enum collapses to default
    assert proposal.data["currency"] == "USD"
    # record_id is carried separately so the frontend PATCHes the rest.
    assert proposal.data["record_id"] == "abc"


def test_delete_activity_proposal(client, monkeypatch):
    headers = auth_headers(register_and_login(client, "ai_activity_del")["access_token"])
    _configure_chat_ai(client, headers)
    activity = client.post(
        "/api/v1/activities", json={"name": "Dinner", "type": "dining"}, headers=headers
    ).json()

    proposal = _chat_with_tool(
        client, headers, monkeypatch, "delete_activity", {"record_id": activity["id"]}
    )
    assert proposal["action"] == "delete_activity"
    assert proposal["record_type"] == "activity"
    assert proposal["data"] == {"record_id": activity["id"]}
    assert client.get(f"/api/v1/activities/{activity['id']}", headers=headers).status_code == 200


def test_new_tools_have_valid_json_schema(client):
    """Every tool schema must be JSON-serialisable for the OpenAI tool format."""
    from app.services.ai_tools import tool_schemas

    blob = json.dumps(tool_schemas())
    for name in [
        "create_expense",
        "update_expense",
        "delete_expense",
        "create_note",
        "update_note",
        "delete_note",
        "create_place",
        "update_place",
        "delete_place",
        "add_place_to_trip",
        "create_activity",
        "update_activity",
        "delete_activity",
        "search_expenses",
        "search_notes",
        "search_places",
        "search_activities",
    ]:
        assert f'"name": "{name}"' in blob or f'"name":"{name}"' in blob
