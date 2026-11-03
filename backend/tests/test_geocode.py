"""GeocodeProvider: provider chain parsing and failure semantics (spec #66)."""

import asyncio

import httpx
import pytest

from app.providers.geocode import GeocodeProvider, GeocodeUnavailableError

PHOTON_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "geometry": {"type": "Point", "coordinates": [103.8607, 1.2834]},
            "properties": {
                "name": "Marina Bay Sands",
                "city": "Singapore",
                "country": "Singapore",
            },
        }
    ],
}

NOMINATIM_PAYLOAD = [
    {
        "lat": "1.2834",
        "lon": "103.8607",
        "display_name": "Marina Bay Sands, Singapore",
    }
]


def _run(handler, *, query: str = "10 Bayfront Ave, Singapore", **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = GeocodeProvider(client=client, **kwargs)
            return await provider.search(query)

    return asyncio.run(run())


def test_photon_parses_first_result():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "photon.example"
        assert request.url.path == "/api/"
        assert request.url.params["q"] == "10 Bayfront Ave, Singapore"
        return httpx.Response(200, json=PHOTON_PAYLOAD)

    result = _run(handler, providers=["photon"], photon_url="https://photon.example")
    assert result is not None
    assert result.lat == 1.2834
    assert result.lon == 103.8607
    assert result.provider == "photon"
    assert result.display_name == "Marina Bay Sands, Singapore, Singapore"


def test_nominatim_parses_first_result_and_sends_policy_headers():
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent")
        seen["language"] = request.headers.get("accept-language")
        seen["path"] = request.url.path
        seen["q"] = request.url.params.get("q")
        seen["format"] = request.url.params.get("format")
        return httpx.Response(200, json=NOMINATIM_PAYLOAD)

    result = _run(
        handler,
        providers=["nominatim"],
        base_url="https://nominatim.example/",
        language="zh-CN",
    )
    assert result is not None
    assert result.lat == 1.2834
    assert result.lon == 103.8607
    assert result.provider == "nominatim"
    assert seen["ua"].startswith("Azmark/")
    assert seen["language"].startswith("zh-CN")
    assert seen["path"] == "/search"
    assert seen["q"] == "10 Bayfront Ave, Singapore"
    assert seen["format"] == "jsonv2"


def test_amap_parses_lon_lat_location():
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["host"] = request.url.host
        seen["address"] = request.url.params.get("address")
        seen["key"] = request.url.params.get("key")
        return httpx.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "geocodes": [
                    {
                        "formatted_address": "上海市黄浦区外滩",
                        "location": "121.490317,31.236305",
                    }
                ],
            },
        )

    result = _run(handler, query="上海外滩", providers=["amap"], amap_key="test-key")
    assert result is not None
    assert result.lat == 31.236305
    assert result.lon == 121.490317
    assert result.provider == "amap"
    assert seen["host"] == "restapi.amap.com"
    assert seen["address"] == "上海外滩"
    assert seen["key"] == "test-key"


def test_chain_falls_back_when_first_provider_is_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "photon.example":
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json=NOMINATIM_PAYLOAD)

    result = _run(
        handler,
        providers=["photon", "nominatim"],
        photon_url="https://photon.example",
        base_url="https://nominatim.example",
    )
    assert result is not None
    assert result.provider == "nominatim"


def test_chain_falls_through_when_amap_key_is_invalid():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "restapi.amap.com":
            return httpx.Response(200, json={"status": "0", "info": "INVALID_USER_KEY"})
        return httpx.Response(200, json=PHOTON_PAYLOAD)

    result = _run(
        handler,
        providers=["amap", "photon"],
        amap_key="bad-key",
        photon_url="https://photon.example",
    )
    assert result is not None
    assert result.provider == "photon"


def test_all_providers_unreachable_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(GeocodeUnavailableError):
        _run(
            handler,
            providers=["photon", "nominatim"],
            photon_url="https://photon.example",
            base_url="https://nominatim.example",
        )


def test_reachable_but_no_match_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "photon.example":
            return httpx.Response(200, json={"type": "FeatureCollection", "features": []})
        return httpx.Response(200, json=[])

    assert (
        _run(
            handler,
            providers=["photon", "nominatim"],
            photon_url="https://photon.example",
            base_url="https://nominatim.example",
        )
        is None
    )


def test_invalid_payloads_degrade_to_none():
    assert (
        _run(
            lambda request: httpx.Response(200, json={"features": [{"geometry": {}}]}),
            providers=["photon"],
            photon_url="https://photon.example",
        )
        is None
    )
    assert (
        _run(
            lambda request: httpx.Response(200, json={"weird": True}),
            providers=["nominatim"],
            base_url="https://nominatim.example",
        )
        is None
    )
    assert (
        _run(
            lambda request: httpx.Response(200, json={"status": "1", "geocodes": [{}]}),
            providers=["amap"],
            amap_key="test-key",
        )
        is None
    )


def test_empty_query_returns_none_without_network_call():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=[])

    assert _run(handler, query="   ", providers=["photon"]) is None
    assert calls == []
