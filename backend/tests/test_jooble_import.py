import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

from backend.app import main
from backend.app.database import JobRepository
from backend.app.main import RefreshService
from backend.app.providers.jooble import JoobleProvider


def make_entries(location: str, page: int, count: int = 20) -> list[dict[str, str]]:
    return [
        {
            "id": f"{location}-{page}-{index}",
            "title": f"Praca {location} {page}-{index}",
            "company": f"Firma {index}",
            "location": location,
            "link": f"https://jobs.example/{location}/{page}/{index}",
            "snippet": "Oferta dla studenta.",
            "salary": "30 zł/h",
            "source": "Partner",
        }
        for index in range(count)
    ]


def test_jooble_import_rotates_and_resumes_pages(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOOBLE_REQUESTS_PER_REFRESH", "3")
    monkeypatch.setenv("JOOBLE_DAILY_REQUEST_LIMIT", "90")
    requests: list[tuple[str, int]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        location, page = body["location"], int(body["page"])
        requests.append((location, page))
        return httpx.Response(200, json={"totalCount": 200, "jobs": make_entries(location, page)})

    async def scenario() -> None:
        repository = JobRepository(tmp_path / "jobs.db")
        repository.initialize()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = JoobleProvider(
                api_key="fake", client=client, keywords="praca",
                locations=["Kraków", "Warszawa"],
            )
            service = RefreshService(repository, [provider])
            first = await service.refresh()
            second = await service.refresh()
        assert first["inserted"] == 60
        assert first["total"] == 60
        assert first["jooble"]["results_received"] == 60
        assert first["jooble"]["requests_this_refresh"] == 3
        assert first["jooble"]["status"] == "batch_complete"
        assert second["inserted"] == 60
        assert second["total"] == 120

    asyncio.run(scenario())
    assert requests == [
        ("Kraków", 1), ("Warszawa", 1), ("Kraków", 2),
        ("Warszawa", 2), ("Kraków", 3), ("Warszawa", 3),
    ]


def test_jooble_failed_page_is_retained_and_retried_manually(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOOBLE_REQUESTS_PER_REFRESH", "5")
    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(json.loads(request.content)["page"])
        requests.append(page)
        if page == 2 and requests.count(2) == 1:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(
            200,
            json={
                "totalCount": 40,
                "jobs": make_entries("Kraków", page),
            },
        )

    async def scenario() -> None:
        repository = JobRepository(tmp_path / "jobs.db")
        repository.initialize()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = RefreshService(
                repository,
                [JoobleProvider(api_key="fake", client=client, locations=["Kraków"])],
            )
            first = await service.refresh()
            assert first["inserted"] == 20
            assert first["jooble"]["requests_this_refresh"] == 2
            assert "ConnectError" in first["provider_errors"][0]
            state = repository.load_provider_state("jooble")
            search = state["searches"][JoobleProvider.search_key(("praca", "Kraków"))]
            assert search["page"] == 2
            assert repository.count() == 20
            second = await service.refresh()
            assert second["inserted"] == 20
            assert second["total"] == 40
            assert second["jooble"]["status"] == "complete"

    asyncio.run(scenario())
    assert requests == [1, 2, 2]


def test_jooble_local_budget_and_utc_reset_preserve_cursor(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOOBLE_DAILY_REQUEST_LIMIT", "2")
    monkeypatch.setenv("JOOBLE_REQUESTS_PER_REFRESH", "10")
    monkeypatch.setattr(main, "_utc_today", lambda: date(2026, 3, 10))
    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(json.loads(request.content)["page"])
        requests.append(page)
        return httpx.Response(
            200,
            json={"totalCount": 60, "jobs": make_entries("Kraków", page)},
        )

    async def scenario() -> None:
        repository = JobRepository(tmp_path / "jobs.db")
        repository.initialize()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = RefreshService(
                repository,
                [JoobleProvider(api_key="fake", client=client, locations=["Kraków"])],
            )
            first = await service.refresh()
            second = await service.refresh()
            assert first["jooble"]["status"] == "daily_limit"
            assert first["jooble"]["requests_remaining"] == 0
            assert second["jooble"]["requests_this_refresh"] == 0

            state = repository.load_provider_state("jooble")
            state["day"] = "2026-03-09"
            monkeypatch.setattr(main, "_utc_today", lambda: date(2026, 3, 11))
            repository.save_provider_state("jooble", state)
            next_day = await service.refresh()
            assert next_day["jooble"]["requests_today"] == 1
            assert next_day["jooble"]["requests_this_refresh"] == 1

    asyncio.run(scenario())
    assert requests == [1, 2, 3]


def test_daily_budget_rolls_over_inside_a_refresh(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOOBLE_DAILY_REQUEST_LIMIT", "2")
    monkeypatch.setenv("JOOBLE_REQUESTS_PER_REFRESH", "2")
    current_day = [date(2026, 3, 10)]
    monkeypatch.setattr(main, "_utc_today", lambda: current_day[0])
    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(json.loads(request.content)["page"])
        requests.append(page)
        current_day[0] = date(2026, 3, 11)
        return httpx.Response(
            200,
            json={"totalCount": 200, "jobs": make_entries("Kraków", page)},
        )

    async def scenario() -> None:
        repository = JobRepository(tmp_path / "jobs.db")
        repository.initialize()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = RefreshService(
                repository,
                [JoobleProvider(api_key="fake", client=client, locations=["Kraków"])],
            )
            result = await service.refresh()
            state = repository.load_provider_state("jooble")
            assert result["jooble"]["requests_this_refresh"] == 2
            assert result["jooble"]["requests_today"] == 1
            assert state["day"] == "2026-03-11"

    asyncio.run(scenario())
    assert requests == [1, 2]


def test_daily_budget_setting_is_capped_at_official_limit(monkeypatch) -> None:
    monkeypatch.setenv("JOOBLE_DAILY_REQUEST_LIMIT", "500")
    assert main._bounded_setting("JOOBLE_DAILY_REQUEST_LIMIT", 90, 100) == 100


def test_refresh_budget_is_capped_at_twenty_requests(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOOBLE_DAILY_REQUEST_LIMIT", "90")
    monkeypatch.setenv("JOOBLE_REQUESTS_PER_REFRESH", "200")
    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(json.loads(request.content)["page"])
        requests.append(page)
        return httpx.Response(
            200,
            json={"totalCount": 1000, "jobs": make_entries("Kraków", page)},
        )

    async def scenario() -> None:
        repository = JobRepository(tmp_path / "jobs.db")
        repository.initialize()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = RefreshService(
                repository,
                [JoobleProvider(api_key="fake", client=client, locations=["Kraków"])],
            )
            result = await service.refresh()
            assert result["jooble"]["requests_this_refresh"] == 20
            assert result["jooble"]["requests_today"] == 20
            assert result["jooble"]["status"] == "batch_complete"

    asyncio.run(scenario())
    assert requests == list(range(1, 21))


def test_jooble_429_pauses_until_utc_reset_and_retries_same_page(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOOBLE_REQUESTS_PER_REFRESH", "5")
    monkeypatch.setattr(main, "_utc_today", lambda: date(2026, 3, 10))
    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(int(json.loads(request.content)["page"]))
        if len(requests) == 1:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={"totalCount": 1, "jobs": make_entries("Kraków", 1, count=1)},
        )

    async def scenario() -> None:
        repository = JobRepository(tmp_path / "jobs.db")
        repository.initialize()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = RefreshService(
                repository,
                [JoobleProvider(api_key="fake", client=client, locations=["Kraków"])],
            )
            limited = await service.refresh()
            assert limited["jooble"]["status"] == "rate_limited"
            assert "00:00 UTC" in limited["jooble"]["paused_reason"]
            paused = await service.refresh()
            assert paused["jooble"]["requests_this_refresh"] == 0

            monkeypatch.setattr(main, "_utc_today", lambda: date(2026, 3, 11))
            resumed = await service.refresh()
            assert resumed["inserted"] == 1
            assert resumed["jooble"]["status"] == "complete"

    asyncio.run(scenario())
    assert requests == [1, 1]


def test_repeated_page_fingerprint_stops_without_duplicate_import(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOOBLE_REQUESTS_PER_REFRESH", "5")
    requests: list[int] = []
    same_page = make_entries("Kraków", 1)

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(json.loads(request.content)["page"])
        requests.append(page)
        return httpx.Response(200, json={
            "totalCount": 100,
            "jobs": same_page if page == 1 else list(reversed(same_page)),
        })

    async def scenario() -> None:
        repository = JobRepository(tmp_path / "jobs.db")
        repository.initialize()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = RefreshService(
                repository,
                [JoobleProvider(api_key="fake", client=client, locations=["Kraków"])],
            )
            result = await service.refresh()
            assert result["inserted"] == 20
            assert result["total"] == 20
            assert result["jooble"]["status"] == "complete"
            assert result["jooble"]["requests_this_refresh"] == 2
            await service.refresh()

            state = repository.load_provider_state("jooble")
            state["day"] = "2026-03-09"
            repository.save_provider_state("jooble", state)
            monkeypatch.setattr(main, "_utc_today", lambda: date(2026, 3, 11))
            restarted = await service.refresh()
            assert restarted["jooble"]["requests_this_refresh"] == 2
            assert restarted["jooble"]["status"] == "complete"

    asyncio.run(scenario())
    assert requests == [1, 2, 1, 2]


def test_refresh_lease_is_exclusive_between_repository_instances(tmp_path) -> None:
    path = tmp_path / "jobs.db"
    first = JobRepository(path)
    second = JobRepository(path)
    first.initialize()

    def acquire(owner: str) -> bool:
        repository = first if owner == "first" else second
        return repository.acquire_refresh_lease("jooble", owner)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(acquire, ["first", "second"]))
    assert sorted(results) == [False, True]
