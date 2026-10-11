"""Tests for the AI chat endpoint and agent tool loop (spec #31, #32, #93)."""

from app.providers.llm import LLMProvider, LLMResponse, LLMToolCall
from app.services.ai_tools import TOOLS, ToolPermission
from tests.conftest import auth_headers, register_and_login


class _ScriptedProvider(LLMProvider):
    """Returns a scripted sequence of responses for deterministic tests."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def chat(self, *, messages, tools=None, temperature=None) -> LLMResponse:
        if self.calls >= len(self._responses):
            return LLMResponse(content="")
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
    assert TOOLS["create_transport"].permission == ToolPermission.WRITE
    assert TOOLS["delete_transport"].permission == ToolPermission.DESTRUCTIVE
