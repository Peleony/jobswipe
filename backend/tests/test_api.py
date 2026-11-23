import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.cleaner import clean_job
from backend.app.database import JobRepository
from backend.app.main import create_app
from backend.app.models import RawJob
from backend.app.providers.base import BaseJobProvider
from backend.app.providers.jooble import JoobleProvider
from backend.app.providers.mock_pl import DEMO_SOURCE, MockPLProvider


class FixtureProvider(BaseJobProvider):
    name = "fixture"

    async def fetch_jobs(self) -> list[RawJob]:
        examples = [
            ("Kelnerka", "Gastro Demo", "Kraków", "30 zł/h", "Wymagana książeczka sanepidowska."),
            ("Magazynier UDT", "Magazyn Demo", "Warszawa", "5 000 zł/mies.", "Uprawnienia UDT."),
            ("Kierowca autobusu", "Transport Demo", "Warszawa", None, "Prawo jazdy kat. D."),
            ("Przedstawiciel handlowy", "Sprzedaż Demo", "Kraków", None, "B2B i wynagrodzenie prowizyjne."),
            ("Asystent biura", "Biuro Demo", "Warszawa", "4 800 zł/mies.", "Bez doświadczenia."),
        ]
        jobs = [
            RawJob(
                title=title,
                company=company,
                city=city,
                url=f"https://example.org/{index}",
                description=description,
                source="fixture",
                salary_raw=salary,
            )
            for index, (title, company, city, salary, description) in enumerate(examples)
        ]
        return jobs + [jobs[0]]


class FailingProvider(BaseJobProvider):
    name = "unavailable"

    async def fetch_jobs(self) -> list[RawJob]:
        raise RuntimeError("error details must not escape")


def test_create_app_loads_project_env_outside_repo_without_overrides(tmp_path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    backend_dir = project_dir / "backend"
    app_dir = backend_dir / "app"
    app_dir.mkdir(parents=True)
    monkeypatch.setattr(config, "__file__", str(app_dir / "config.py"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JOOBLE_API_KEY", "placeholder")
    monkeypatch.delenv("JOOBLE_API_KEY")
    monkeypatch.setenv("JOOBLE_API_BASE_URL", "https://process.example/api")
    monkeypatch.setenv("DEMO_DATA", "auto")
    monkeypatch.setenv("CORS_ORIGINS", "placeholder")
    monkeypatch.delenv("CORS_ORIGINS")
    (project_dir / ".env").write_text(
        "JOOBLE_API_KEY=test-key\nJOOBLE_API_BASE_URL=https://project.example/api\n",
        encoding="utf-8-sig",
    )
    (backend_dir / ".env").write_text(
        "JOOBLE_API_KEY=backend-key\nCORS_ORIGINS=http://localhost:8888\n", encoding="utf-8"
    )

    app = create_app(tmp_path / "jobs.db", auto_seed=False)
    jooble, = app.state.refresh_service.providers
    assert jooble.name == "jooble"
    assert jooble.api_key == "test-key"
    assert jooble.base_url == "https://process.example/api"
    with TestClient(app) as client:
        response = client.get("/healthz", headers={"Origin": "http://localhost:8888"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:8888"


@pytest.mark.parametrize(("mode", "key", "providers"), [
    ("auto", "", ["demo"]),
    ("true", "", ["demo"]),
    ("false", "", []),
    ("auto", "test-key", ["jooble"]),
    ("true", "test-key", ["jooble"]),
    ("false", "test-key", ["jooble"]),
])
def test_configured_demo_mode(tmp_path, monkeypatch, mode, key, providers) -> None:
    monkeypatch.setenv("DEMO_DATA", mode)
    monkeypatch.setenv("JOOBLE_API_KEY", key)
    app = create_app(tmp_path / "jobs.db", auto_seed=False)
    assert [provider.name for provider in app.state.refresh_service.providers] == providers


def add_demo_job(repository: JobRepository) -> None:
    example = asyncio.run(MockPLProvider().fetch_jobs())[0]
    repository.upsert_many([clean_job(example)])


def test_startup_and_refresh_purge_demo_without_removing_other_sources(tmp_path) -> None:
    db = tmp_path / "jobs.db"
    repository = JobRepository(db)
    repository.initialize()
    add_demo_job(repository)
    live = asyncio.run(FixtureProvider().fetch_jobs())[0]
    repository.upsert_many([clean_job(live)])

    app = create_app(db, [FixtureProvider()], auto_seed=False)
    with TestClient(app) as client:
        assert [job["source"] for job in client.get("/api/jobs").json()] == [live.source]
        add_demo_job(repository)
        assert repository.count() == 2
        refresh = client.post("/api/jobs/refresh")
        assert refresh.status_code == 200
        jobs = client.get("/api/jobs").json()
        assert len(jobs) == 5
        assert {job["source"] for job in jobs} == {live.source}


def test_seed_purges_demo_when_disabled(tmp_path, monkeypatch) -> None:
    db = tmp_path / "jobs.db"
    repository = JobRepository(db)
    repository.initialize()
    add_demo_job(repository)
    assert repository.list_jobs()[0].source == DEMO_SOURCE
    monkeypatch.setenv("DATABASE_PATH", str(db))
    monkeypatch.setenv("DEMO_DATA", "false")
    monkeypatch.setenv("JOOBLE_API_KEY", "")
    seed = Path(__file__).resolve().parents[1] / "seed.py"
    run = subprocess.run(
        [sys.executable, str(seed)], cwd=tmp_path, capture_output=True, text=True, check=True, timeout=10,
    )
    assert json.loads(run.stdout)["unique_jobs"] == 0
    assert repository.count() == 0


def test_filters_support_bracket_arrays_city_salary_and_exclusions(tmp_path) -> None:
    app = create_app(tmp_path / "jobs.db", [FixtureProvider()], auto_seed=True)
    with TestClient(app) as client:
        assert client.get("/api/jobs?city=KRAK%C3%93W").json()[0]["city"] == "Kraków"
        assert client.get("/api/jobs?city=Warszawa").json()
        assert client.get("/api/jobs?city=Kraków&require_salary=true").json()[0]["title"] == "Kelnerka"

        safe_city_jobs = client.get(
            "/api/jobs?city=Warszawa&require_salary=true&blocked_tags%5B%5D=udt"
        ).json()
        assert [job["title"] for job in safe_city_jobs] == ["Asystent biura"]

        without_transit = client.get(
            "/api/jobs?blocked_industries%5B%5D=transport"
        ).json()
        assert all("transport" not in job["industries"] for job in without_transit)

        first = client.get("/api/jobs?city=Kraków").json()[0]
        excluded = client.get(f"/api/jobs?exclude_hashes%5B%5D={first['hash']}").json()
        assert first["hash"] not in {job["hash"] for job in excluded}


def test_refresh_is_idempotent_and_provider_failure_keeps_other_results(tmp_path) -> None:
    app = create_app(
        tmp_path / "jobs.db", [FixtureProvider(), FailingProvider()], auto_seed=True
    )
    with TestClient(app) as client:
        before = client.get("/api/jobs").json()
        assert len(before) == 5
        assert app.state.repository.count() == 5

        refresh = client.post("/api/jobs/refresh")
        assert refresh.status_code == 200
        assert refresh.json() == {
            "fetched": 6,
            "inserted": 0,
            "updated": 5,
            "total": 5,
            "provider_errors": ["unavailable: tymczasowo niedostępny (RuntimeError)"],
        }
        assert app.state.repository.count() == 5
        assert client.get("/api/jobs").json()
        assert "error details" not in refresh.text


@pytest.mark.parametrize("diagnostic", ["HTTP 403", "ConnectError"])
def test_refresh_logs_and_returns_safe_jooble_diagnostics(tmp_path, caplog, diagnostic) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if diagnostic == "ConnectError":
            raise httpx.ConnectError(f"Could not reach {request.url}", request=request)
        return httpx.Response(403, text=f"Denied {request.url}")

    external_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    jooble = JoobleProvider(api_key="fake-api-key", client=external_client)
    app = create_app(tmp_path / "jobs.db", [FixtureProvider(), jooble], auto_seed=False)
    with TestClient(app) as client:
        try:
            response = client.post("/api/jobs/refresh")
        finally:
            client.portal.call(external_client.aclose)

    assert response.status_code == 200
    assert response.json()["inserted"] == 5
    error, = response.json()["provider_errors"]
    assert error.startswith("jooble: tymczasowo niedostępny")
    assert diagnostic in error
    assert error in caplog.messages
    assert "fake-api-key" not in response.text
    assert "fake-api-key" not in caplog.text


def test_search_excludes_large_history_before_applying_limit(tmp_path) -> None:
    app = create_app(tmp_path / "jobs.db", [FixtureProvider()], auto_seed=False)
    examples = asyncio.run(FixtureProvider().fetch_jobs())
    matching = [
        clean_job(examples[0].model_copy(update={"title": f"Kelnerka {index}"}))
        for index in range(1051)
    ]
    matching.sort(key=lambda job: job.hash)
    with TestClient(app) as client:
        app.state.repository.upsert_many([*matching, *map(clean_job, examples[1:5])])
        filters = {
            "city": " KRAKÓW ",
            "require_salary": True,
            "blocked_tags": ["prowizja_scam"],
            "blocked_industries": ["transport"],
        }
        excluded = [job.hash for job in matching[:1000]]
        response = client.post("/api/jobs/search", json={**filters, "exclude_hashes": excluded})
        assert response.status_code == 200
        returned = {job["hash"] for job in response.json()}
        eligible = {job.hash for job in matching[1000:]}
        assert len(response.json()) == len(returned) == 50
        assert returned <= eligible

        remaining = client.post("/api/jobs/search", json={
            **filters, "exclude_hashes": [*excluded, *returned],
        })
        assert remaining.status_code == 200
        assert [job["hash"] for job in remaining.json()] == list(eligible - returned)


@pytest.mark.parametrize("payload", [
    {"require_salary": "true"},
    {"exclude_hashes": [{"hash": "0123456789abcdef"}]},
    {"exclude_hashes": ["not-a-hash"]},
    {"master_cv": "private"},
])
def test_search_rejects_invalid_or_extra_fields(tmp_path, payload) -> None:
    app = create_app(tmp_path / "jobs.db", [], auto_seed=False)
    with TestClient(app) as client:
        assert client.post("/api/jobs/search", json=payload).status_code == 422


def test_empty_database_without_auto_seed_returns_empty_list(tmp_path) -> None:
    app = create_app(tmp_path / "empty.db", [FixtureProvider()], auto_seed=False)
    with TestClient(app) as client:
        response = client.get("/api/jobs?city=Nieistniejące")
        assert response.status_code == 200
        assert response.json() == []
