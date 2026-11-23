import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .cleaner import clean_job
from .database import JobRepository, configured_database_path
from .models import CleanJob
from .providers.base import BaseJobProvider
from .providers.jooble import JoobleProvider
from .providers.mock_pl import MockPLProvider


logger = logging.getLogger("jobswipe.refresh")


class RefreshService:
    def __init__(self, repository: JobRepository, providers: list[BaseJobProvider]):
        self.repository = repository
        self.providers = providers
        self._lock = asyncio.Lock()

    async def refresh(self) -> dict[str, Any]:
        async with self._lock:
            fetched = 0
            provider_errors: list[str] = []
            unique_jobs: dict[str, CleanJob] = {}
            for provider in self.providers:
                try:
                    raw_jobs = await provider.fetch_jobs()
                    fetched += len(raw_jobs)
                    for raw_job in raw_jobs:
                        cleaned = clean_job(raw_job)
                        unique_jobs[cleaned.hash] = cleaned
                except Exception as exc:
                    logger.error("Provider %s failed (%s)", provider.name, type(exc).__name__)
                    provider_errors.append(f"{provider.name}: tymczasowo niedostępny")

            inserted, updated = self.repository.upsert_many(unique_jobs.values())
            return {
                "fetched": fetched,
                "inserted": inserted,
                "updated": updated,
                "provider_errors": provider_errors,
            }


def _configured_providers() -> list[BaseJobProvider]:
    providers: list[BaseJobProvider] = [MockPLProvider()]
    if os.getenv("JOOBLE_API_KEY", "").strip():
        providers.append(JoobleProvider())
    return providers


def create_app(
    database_path: str | os.PathLike[str] | None = None,
    providers: list[BaseJobProvider] | None = None,
    *,
    auto_seed: bool = True,
) -> FastAPI:
    repository = JobRepository(database_path or configured_database_path())
    service = RefreshService(repository, _configured_providers() if providers is None else providers)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repository.initialize()
        if auto_seed and repository.count() == 0:
            result = await service.refresh()
            if result["provider_errors"]:
                logger.error("Initial listing refresh had provider errors: %s", result["provider_errors"])
        yield

    app = FastAPI(title="JobSwipe API", version="1.0.0", lifespan=lifespan)
    app.state.repository = repository
    app.state.refresh_service = service

    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/jobs", response_model=list[CleanJob])
    async def get_jobs(
        city: str | None = None,
        require_salary: bool = False,
        blocked_tags: list[str] = Query(default=[]),
        blocked_tags_bracket: list[str] = Query(default=[], alias="blocked_tags[]"),
        blocked_industries: list[str] = Query(default=[]),
        blocked_industries_bracket: list[str] = Query(default=[], alias="blocked_industries[]"),
        exclude_hashes: list[str] = Query(default=[]),
        exclude_hashes_bracket: list[str] = Query(default=[], alias="exclude_hashes[]"),
    ) -> list[CleanJob]:
        return repository.list_jobs(
            city=city.strip() if city and city.strip() else None,
            blocked_tags=list(dict.fromkeys(blocked_tags + blocked_tags_bracket)),
            blocked_industries=list(dict.fromkeys(blocked_industries + blocked_industries_bracket)),
            exclude_hashes=list(dict.fromkeys(exclude_hashes + exclude_hashes_bracket)),
            require_salary=require_salary,
            limit=50,
        )

    @app.post("/api/jobs/refresh")
    async def refresh_jobs() -> dict[str, Any]:
        return await service.refresh()

    return app


app = create_app()
