import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from .cleaner import clean_job
from .config import load_local_env
from .database import JobRepository, configured_database_path
from .models import CleanJob
from .providers.base import BaseJobProvider, ProviderError
from .providers.jooble import JoobleProvider, RESULTS_PER_PAGE
from .providers.mock_pl import DEMO_SOURCE, MockPLProvider


logger = logging.getLogger("jobswipe.refresh")
REFRESH_LEASE_SECONDS = 120


class JobSearch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    city: str = ""
    require_salary: bool = False
    blocked_tags: list[str] = Field(default_factory=list)
    blocked_industries: list[str] = Field(default_factory=list)
    exclude_hashes: list[Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]] = Field(
        default_factory=list
    )


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _bounded_setting(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(1, min(value, maximum))


def _new_jooble_state(day: str, searches: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "day": day,
        "requests_today": 0,
        "paused_until": None,
        "search_index": 0,
        "searches": {
            JoobleProvider.search_key(search): {
                "page": 1,
                "done": False,
                "fingerprints": [],
            }
            for search in searches
        },
    }


class RefreshService:
    def __init__(self, repository: JobRepository, providers: list[BaseJobProvider]):
        self.repository = repository
        self.providers = providers
        self._lock = asyncio.Lock()

    def purge_disabled_demo(self) -> None:
        if not any(isinstance(provider, MockPLProvider) for provider in self.providers):
            self.repository.delete_by_source(DEMO_SOURCE)

    async def _refresh_jooble(self, provider: JoobleProvider) -> dict[str, Any]:
        today = _utc_today().isoformat()
        daily_limit = _bounded_setting("JOOBLE_DAILY_REQUEST_LIMIT", 90, 100)
        per_refresh = _bounded_setting("JOOBLE_REQUESTS_PER_REFRESH", 20, 20)
        owner = uuid.uuid4().hex
        if not self.repository.acquire_refresh_lease(provider.name, owner, REFRESH_LEASE_SECONDS):
            state = self.repository.load_provider_state(provider.name)
            if not isinstance(state, dict):
                state = _new_jooble_state(today, provider.searches)
            return self._jooble_summary(
                state, daily_limit, 0, 0, 0, "busy",
                "Inny proces aktualizuje już Jooble. Spróbuj ponownie za chwilę.",
            )

        try:
            state = self.repository.load_provider_state(provider.name)
            if not isinstance(state, dict):
                state = _new_jooble_state(today, provider.searches)
            searches_state = state.get("searches")
            if not isinstance(searches_state, dict):
                searches_state = {}
                state["searches"] = searches_state
            for search in provider.searches:
                searches_state.setdefault(
                    provider.search_key(search),
                    {"page": 1, "done": False, "fingerprints": []},
                )
            if state.get("day") != today:
                for search in provider.searches:
                    search_state = searches_state[provider.search_key(search)]
                    if search_state.get("done"):
                        searches_state[provider.search_key(search)] = {
                            "page": 1,
                            "done": False,
                            "fingerprints": [],
                        }
                state["day"] = today
                state["requests_today"] = 0
                state["paused_until"] = None
                state.pop("pause_reason", None)
            requests_today = int(state.get("requests_today", 0))
            state["requests_today"] = requests_today
            state["paused_until"] = state.get("paused_until")
            state["search_index"] = int(state.get("search_index", 0)) % len(provider.searches)
            self.repository.save_provider_state(provider.name, state)

            if state.get("paused_until") and str(state["paused_until"]) > today:
                return self._jooble_summary(
                    state, daily_limit, 0, 0, 0, "rate_limited",
                    "Jooble osiągnął dzienny limit API; import wznowi się po 00:00 UTC.",
                )
            if requests_today >= daily_limit:
                return self._jooble_summary(
                    state, daily_limit, 0, 0, 0, "daily_limit",
                    "Osiągnięto lokalny limit dzienny; licznik wyzeruje się o 00:00 UTC.",
                )

            state.pop("pause_reason", None)
            self.repository.save_provider_state(provider.name, state)
            request_budget = min(per_refresh, daily_limit - requests_today)
            requests_made = fetched = received = inserted = updated = 0
            seen_hashes: set[str] = set()
            last_failure: str | None = None
            failure_status: str | None = None

            for _ in range(request_budget):
                request_day = _utc_today().isoformat()
                if state.get("day") != request_day:
                    for search in provider.searches:
                        search_key = provider.search_key(search)
                        if searches_state[search_key].get("done"):
                            searches_state[search_key] = {
                                "page": 1,
                                "done": False,
                                "fingerprints": [],
                            }
                    state["day"] = request_day
                    state["requests_today"] = 0
                    state["paused_until"] = None
                    state.pop("pause_reason", None)
                    requests_today = 0
                    self.repository.save_provider_state(provider.name, state)

                search_index = int(state["search_index"])
                selected = None
                for offset in range(len(provider.searches)):
                    candidate = (search_index + offset) % len(provider.searches)
                    candidate_key = provider.search_key(provider.searches[candidate])
                    if not searches_state[candidate_key].get("done"):
                        selected = candidate
                        break
                if selected is None:
                    break

                search = provider.searches[selected]
                search_key = provider.search_key(search)
                search_state = searches_state[search_key]
                page_number = int(search_state.get("page", 1))
                requests_today += 1
                requests_made += 1
                state["requests_today"] = requests_today
                self.repository.save_provider_state(provider.name, state)
                if not self.repository.renew_refresh_lease(
                    provider.name, owner, REFRESH_LEASE_SECONDS
                ):
                    last_failure = "Utracono blokadę odświeżania; nie rozpoczęto kolejnej strony."
                    break

                try:
                    page = await provider.fetch_page(search, page_number)
                except ProviderError as exc:
                    last_failure = str(exc)
                    if "HTTP 429" in last_failure:
                        tomorrow = (
                            date.fromisoformat(request_day) + timedelta(days=1)
                        ).isoformat()
                        state["paused_until"] = tomorrow
                        state["pause_reason"] = (
                            "Jooble zwrócił HTTP 429; import wznowi się po 00:00 UTC."
                        )
                        failure_status = "rate_limited"
                    elif "HTTP 403" in last_failure:
                        state["pause_reason"] = (
                            "Jooble zwrócił HTTP 403. Sprawdź klucz i dostęp do polskiego endpointu."
                        )
                        failure_status = "access_denied"
                    else:
                        state["pause_reason"] = (
                            f"{last_failure}; nieudana strona zostanie ponowiona przy następnym ręcznym odświeżeniu."
                        )
                        failure_status = "request_error"
                    self.repository.save_provider_state(provider.name, state)
                    break

                repeated_page = bool(
                    page.fingerprint
                    and page.fingerprint in search_state.get("fingerprints", [])
                )
                cleaned_jobs: list[CleanJob] = []
                if not repeated_page:
                    received += page.result_count
                    for raw_job in page.jobs:
                        fetched += 1
                        cleaned = clean_job(raw_job)
                        if cleaned.hash not in seen_hashes:
                            seen_hashes.add(cleaned.hash)
                            cleaned_jobs.append(cleaned)

                fingerprints = list(search_state.get("fingerprints", []))
                if page.fingerprint and not repeated_page:
                    fingerprints.append(page.fingerprint)
                search_state["fingerprints"] = fingerprints[-1000:]
                if (
                    repeated_page
                    or page.result_count == 0
                    or page.result_count < RESULTS_PER_PAGE
                    or (
                        page.total_count is not None
                        and page_number * RESULTS_PER_PAGE >= page.total_count
                    )
                ):
                    search_state["done"] = True
                else:
                    search_state["page"] = page_number + 1
                state["search_index"] = (selected + 1) % len(provider.searches)
                page_inserted, page_updated = self.repository.commit_provider_page(
                    provider.name, state, cleaned_jobs
                )
                inserted += page_inserted
                updated += page_updated

            requests_today = int(state["requests_today"])
            all_done = all(
                searches_state[provider.search_key(search)].get("done")
                for search in provider.searches
            )
            if last_failure:
                message = f"{provider.name}: tymczasowo niedostępny ({last_failure})"
                provider_errors = [message]
                reason = str(state.get("pause_reason") or last_failure)
                status = failure_status or "refresh_error"
                logger.error("%s", message)
            elif all_done:
                provider_errors = []
                reason = "Wszystkie skonfigurowane strony wyników są pobrane; nowy cykl zacznie się następnego dnia UTC."
                status = "complete"
            elif requests_today >= daily_limit:
                provider_errors = []
                reason = "Osiągnięto lokalny limit dzienny; licznik wyzeruje się o 00:00 UTC."
                status = "daily_limit"
            elif requests_made >= request_budget:
                provider_errors = []
                reason = (
                    f"Partia zakończona po {requests_made} zapytaniach; kliknij Odśwież, "
                    "aby pobrać następną partię."
                )
                status = "batch_complete"
            else:
                provider_errors = []
                reason = None
                status = "complete"

            summary = self._jooble_summary(
                state, daily_limit, requests_made, fetched, inserted, status, reason, received
            )
            summary["updated"] = updated
            summary["provider_errors"] = provider_errors
            return summary
        finally:
            try:
                await provider.close()
            finally:
                self.repository.release_refresh_lease(provider.name, owner)

    @staticmethod
    def _jooble_summary(
        state: dict[str, object],
        daily_limit: int,
        requests_made: int,
        fetched: int,
        inserted: int,
        status: str,
        paused_reason: str | None,
        received: int = 0,
    ) -> dict[str, Any]:
        requests_today = int(state.get("requests_today", 0))
        return {
            "requests_this_refresh": requests_made,
            "requests_today": requests_today,
            "daily_request_limit": daily_limit,
            "requests_remaining": max(0, daily_limit - requests_today),
            "status": status,
            "paused_reason": paused_reason,
            "results_received": received,
            "fetched": fetched,
            "inserted": inserted,
            "updated": 0,
        }

    async def refresh(self) -> dict[str, Any]:
        async with self._lock:
            self.purge_disabled_demo()
            fetched = 0
            provider_errors: list[str] = []
            inserted = 0
            updated = 0
            jooble_summary: dict[str, Any] | None = None
            unique_jobs: dict[str, CleanJob] = {}
            for provider in self.providers:
                try:
                    if isinstance(provider, JoobleProvider):
                        jooble_summary = await self._refresh_jooble(provider)
                        fetched += jooble_summary["fetched"]
                        inserted += jooble_summary["inserted"]
                        updated += jooble_summary["updated"]
                        provider_errors.extend(jooble_summary.get("provider_errors", []))
                        continue
                    raw_jobs = await provider.fetch_jobs()
                    fetched += len(raw_jobs)
                    for raw_job in raw_jobs:
                        cleaned = clean_job(raw_job)
                        unique_jobs[cleaned.hash] = cleaned
                except Exception as exc:
                    detail = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
                    message = f"{provider.name}: tymczasowo niedostępny ({detail})"
                    logger.error("%s", message)
                    provider_errors.append(message)

            generic_inserted, generic_updated = self.repository.upsert_many(unique_jobs.values())
            inserted += generic_inserted
            updated += generic_updated
            result = {
                "fetched": fetched,
                "inserted": inserted,
                "updated": updated,
                "total": self.repository.count(),
                "provider_errors": provider_errors,
            }
            if jooble_summary is not None:
                jooble_summary.pop("provider_errors", None)
                result["jooble"] = jooble_summary
            return result


def _configured_providers() -> list[BaseJobProvider]:
    if os.getenv("JOOBLE_API_KEY", "").strip():
        return [JoobleProvider()]
    if os.getenv("DEMO_DATA", "auto").strip().lower() in {"auto", "true"}:
        return [MockPLProvider()]
    return []


def create_app(
    database_path: str | os.PathLike[str] | None = None,
    providers: list[BaseJobProvider] | None = None,
    *,
    auto_seed: bool = True,
) -> FastAPI:
    load_local_env()
    repository = JobRepository(database_path or configured_database_path())
    service = RefreshService(repository, _configured_providers() if providers is None else providers)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repository.initialize()
        service.purge_disabled_demo()
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

    @app.post("/api/jobs/search", response_model=list[CleanJob])
    async def search_jobs(filters: JobSearch) -> list[CleanJob]:
        return repository.list_jobs(
            city=filters.city.strip() or None,
            blocked_tags=list(dict.fromkeys(filters.blocked_tags)),
            blocked_industries=list(dict.fromkeys(filters.blocked_industries)),
            exclude_hashes=list(dict.fromkeys(filters.exclude_hashes)),
            require_salary=filters.require_salary,
            limit=50,
        )

    @app.post("/api/jobs/refresh")
    async def refresh_jobs() -> dict[str, Any]:
        return await service.refresh()

    return app


app = create_app()
