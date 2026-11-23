from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.models import RawJob
from backend.app.providers.base import BaseJobProvider


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
            "provider_errors": ["unavailable: tymczasowo niedostępny"],
        }
        assert app.state.repository.count() == 5
        assert client.get("/api/jobs").json()
        assert "error details" not in refresh.text


def test_empty_database_without_auto_seed_returns_empty_list(tmp_path) -> None:
    app = create_app(tmp_path / "empty.db", [FixtureProvider()], auto_seed=False)
    with TestClient(app) as client:
        response = client.get("/api/jobs?city=Nieistniejące")
        assert response.status_code == 200
        assert response.json() == []
