"""Train field inference: seat position, carrier and web lookup (spec #13/#37)."""

import asyncio
import uuid

import pytest

from app.providers.search import (
    BraveProvider,
    SearchResult,
    SearxngProvider,
    TavilyProvider,
    build_search_provider,
)
from app.services import ai_tools
from app.services import search as search_service
from app.services.seating import infer_train_seat_type
from tests.conftest import auth_headers, register_and_login


@pytest.mark.parametrize(
    ("seat", "expected"),
    [
        ("12A", "window"),
        ("12F", "window"),
        ("05车12F号", "window"),
        ("13C", "aisle"),
        ("13D", "aisle"),
        ("12B", "middle"),
        ("5车12号下铺", "sleeper"),
        ("上铺", "sleeper"),
        ("无座", "standing"),
        ("12", None),
        (None, None),
    ],
)
def test_infer_train_seat_type(seat, expected):
    assert infer_train_seat_type(seat) == expected


def test_fill_inferred_fields_train():
    data = ai_tools._fill_inferred_fields("train", {"service_number": "g1234", "seat": "12F"})
    assert data["train_type"] == "高铁"
    assert data["carrier"] == "中国铁路"
    assert data["seat_type"] == "window"


def test_fill_inferred_fields_keeps_explicit_values():
    data = ai_tools._fill_inferred_fields(
        "train",
        {"service_number": "G1234", "carrier": "JR East", "seat": "12F", "seat_type": "aisle"},
    )
    assert data["carrier"] == "JR East"
    assert data["seat_type"] == "aisle"


def test_create_train_infers_seat_type(client):
    token = register_and_login(client, "seat_infer")["access_token"]
    headers = auth_headers(token)
    payload = {
        "origin": "北京南",
        "destination": "上海虹桥",
        "service_number": "G1",
        "seat": "05车12F号",
    }
    created = client.post("/api/v1/trains", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["seat_type"] == "window"

    updated = client.patch(
        f"/api/v1/trains/{created.json()['id']}", json={"seat": "13C"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["seat_type"] == "aisle"


def test_build_search_provider():
    assert isinstance(build_search_provider(name="tavily", api_key="k"), TavilyProvider)
    assert isinstance(build_search_provider(name="brave", api_key="k"), BraveProvider)
    assert isinstance(
        build_search_provider(name="searxng", base_url="https://s.example"), SearxngProvider
    )
    assert build_search_provider(name="tavily") is None
    assert build_search_provider(name="nope", api_key="k") is None


def test_resolve_search_provider(monkeypatch):
    monkeypatch.setattr(search_service.settings, "search_provider", "")
    monkeypatch.setattr(search_service.settings, "search_api_key", "")
    assert search_service.resolve_search_provider({}) is None
    provider = search_service.resolve_search_provider({"tavily": "key"})
    assert isinstance(provider, TavilyProvider)


def test_lookup_train_without_provider(db, monkeypatch):
    monkeypatch.setattr(search_service, "resolve_search_provider", lambda keys: None)
    result = asyncio.run(ai_tools._lookup_train(db, uuid.uuid4(), {"train_number": "G1"}))
    assert result["error"] == "no_search_provider"


def test_lookup_train_requires_number_or_route(db):
    result = asyncio.run(ai_tools._lookup_train(db, uuid.uuid4(), {"origin": "北京"}))
    assert "train_number" in result["error"]


def test_lookup_train_returns_results(db, monkeypatch):
    class FakeProvider:
        name = "fake"

        async def search(self, query, *, max_results=6):
            assert "G1" in query
            return [SearchResult("G1 时刻表", "https://example.com", "到达 12:28")]

    monkeypatch.setattr(search_service, "resolve_search_provider", lambda keys: FakeProvider())
    result = asyncio.run(
        ai_tools._lookup_train(
            db,
            uuid.uuid4(),
            {"train_number": "G1", "date": "2026-05-01", "origin": "北京", "destination": "上海"},
        )
    )
    assert result["provider"] == "fake"
    assert result["results"][0]["snippet"] == "到达 12:28"
    assert "2026-05-01" in result["query"]
