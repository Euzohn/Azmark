"""GeocodeProvider: Nominatim parsing and graceful degradation (spec #66)."""

import asyncio

import httpx

from app.providers.geocode import GeocodeProvider


def _search(handler, *, query: str = "10 Bayfront Ave, Singapore"):
    async def run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = GeocodeProvider("https://nominatim.example/", client=client)
            return await provider.search(query)

    return asyncio.run(run())


def test_geocode_parses_first_result():
    result = _search(
        lambda request: httpx.Response(
            200,
            json=[
                {
                    "lat": "1.2834",
                    "lon": "103.8607",
                    "display_name": "Marina Bay Sands, Singapore",
                }
            ],
        )
    )
    assert result is not None
    assert result.lat == 1.2834
    assert result.lon == 103.8607
    assert result.display_name == "Marina Bay Sands, Singapore"


def test_geocode_empty_and_invalid_payloads_degrade_to_none():
    assert _search(lambda request: httpx.Response(200, json=[])) is None
    assert _search(lambda request: httpx.Response(200, json={"weird": True})) is None
    assert _search(lambda request: httpx.Response(200, json=[{"lat": "nope", "lon": "x"}])) is None


def test_geocode_http_error_and_empty_query_degrade_to_none():
    assert _search(lambda request: httpx.Response(500)) is None
    assert _search(lambda request: httpx.Response(200, json=[]), query="   ") is None


def test_geocode_sends_policy_required_headers_and_params():
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent")
        seen["path"] = request.url.path
        seen["q"] = request.url.params.get("q")
        seen["format"] = request.url.params.get("format")
        return httpx.Response(200, json=[])

    _search(handler)
    assert seen["ua"].startswith("Azmark/")
    assert seen["path"] == "/search"
    assert seen["q"] == "10 Bayfront Ave, Singapore"
    assert seen["format"] == "jsonv2"
