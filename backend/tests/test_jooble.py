import asyncio
import json

import httpx
import pytest

from backend.app.providers.base import ProviderError
from backend.app.providers.jooble import JoobleProvider


def test_jooble_maps_documented_fields_with_mock_transport() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Kelnerka",
                        "company": "Demo Bistro",
                        "location": "Kraków",
                        "link": "https://jobs.example/oferta/1",
                        "snippet": "Praca w kawiarni",
                        "source": "Partner",
                        "salary": "30 zł/h",
                    },
                    {"title": "Niebezpieczny link", "link": "http://jobs.example/oferta/2"},
                    {"title": "Brak tytułu", "link": "https://jobs.example/oferta/3"},
                    None,
                ]
            },
        )

    async def fetch() -> list[object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = JoobleProvider(api_key="test-key", client=client)
            return await provider.fetch_jobs()

    jobs = asyncio.run(fetch())

    assert len(requests) == 3
    assert all(request.method == "POST" for request in requests)
    assert all(str(request.url) == "https://jooble.org/api/test-key" for request in requests)
    assert [json.loads(request.content)["location"] for request in requests] == [
        "Kraków",
        "Warszawa",
        "Wrocław",
    ]
    assert len(jobs) == 6
    assert jobs[0].title == "Kelnerka"
    assert jobs[0].company == "Demo Bistro"
    assert jobs[0].city == "Kraków"
    assert jobs[0].url == "https://jobs.example/oferta/1"
    assert jobs[0].description == "Praca w kawiarni"
    assert jobs[0].source == "Partner"
    assert jobs[0].salary_raw == "30 zł/h"
    assert jobs[1].company == "Nie podano"


def test_jooble_http_failure_is_safe_and_does_not_expose_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="secret=test-key")

    async def fetch() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await JoobleProvider(api_key="test-key", client=client).fetch_jobs()

    with pytest.raises(ProviderError, match="Jooble returned HTTP 403") as error:
        asyncio.run(fetch())
    assert "test-key" not in str(error.value)


def test_jooble_unexpected_response_is_reported_as_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    async def fetch() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await JoobleProvider(api_key="test-key", client=client).fetch_jobs()

    with pytest.raises(ProviderError, match="Jooble returned an unexpected response"):
        asyncio.run(fetch())


def test_jooble_does_not_make_requests_without_api_key() -> None:
    async def fetch() -> list[object]:
        def unexpected_request(request: httpx.Request) -> httpx.Response:
            pytest.fail("unexpected request")

        async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request)) as client:
            return await JoobleProvider(api_key="", client=client).fetch_jobs()

    assert asyncio.run(fetch()) == []
