import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from ..models import RawJob
from .base import BaseJobProvider, ProviderError


DEFAULT_LOCATIONS = ("Kraków", "Warszawa", "Wrocław", "Polska")
RESULTS_PER_PAGE = 20


@dataclass(frozen=True)
class JooblePage:
    jobs: list[RawJob]
    result_count: int
    total_count: int | None
    fingerprint: str


class JoobleProvider(BaseJobProvider):
    name = "jooble"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 12,
        client: httpx.AsyncClient | None = None,
        *,
        keywords: str | None = None,
        locations: tuple[str, ...] | list[str] | None = None,
    ):
        self.api_key = (api_key if api_key is not None else os.getenv("JOOBLE_API_KEY", "")).strip()
        self.base_url = (
            base_url or os.getenv("JOOBLE_API_BASE_URL", "https://pl.jooble.org/api")
        ).rstrip("/")
        self.timeout = timeout
        self.client = client
        self._owned_client: httpx.AsyncClient | None = None
        self.keywords = (keywords or os.getenv("JOOBLE_KEYWORDS", "praca")).strip() or "praca"
        configured_locations = locations
        if configured_locations is None:
            configured_locations = tuple(
                item.strip()
                for item in os.getenv("JOOBLE_LOCATIONS", ",".join(DEFAULT_LOCATIONS)).split(",")
                if item.strip()
            )
        self.locations = tuple(dict.fromkeys(configured_locations)) or DEFAULT_LOCATIONS

    @staticmethod
    def search_key(search: tuple[str, str]) -> str:
        return json.dumps(search, ensure_ascii=False, separators=(",", ":"))

    @property
    def searches(self) -> list[tuple[str, str]]:
        return [(self.keywords, location) for location in self.locations]

    async def fetch_page(self, search: tuple[str, str], page: int) -> JooblePage:
        if not self.api_key:
            raise ProviderError("Jooble API key is missing")

        if self.client is not None:
            return await self._fetch_page_with_client(self.client, search, page)
        if self._owned_client is None or self._owned_client.is_closed:
            self._owned_client = httpx.AsyncClient(timeout=self.timeout)
        return await self._fetch_page_with_client(self._owned_client, search, page)

    async def close(self) -> None:
        if self._owned_client is not None:
            await self._owned_client.aclose()
            self._owned_client = None

    async def _fetch_page_with_client(
        self,
        client: httpx.AsyncClient,
        search: tuple[str, str],
        page: int,
    ) -> JooblePage:
        keywords, location = search
        try:
            async with asyncio.timeout(self.timeout):
                response = await client.post(
                    f"{self.base_url}/{self.api_key}",
                    json={
                        "keywords": keywords,
                        "location": location,
                        "page": str(page),
                        "ResultOnPage": RESULTS_PER_PAGE,
                        "companysearch": False,
                    },
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Jooble returned HTTP {exc.response.status_code}") from None
        except (httpx.HTTPError, ValueError, TimeoutError) as exc:
            raise ProviderError(f"Jooble request or response failed ({type(exc).__name__})") from None

        entries = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise ProviderError("Jooble returned an unexpected response")
        total_count = payload.get("totalCount")
        try:
            total_count = int(total_count) if total_count is not None else None
        except (TypeError, ValueError):
            total_count = None

        identities = []
        jobs = []
        for entry in entries:
            if not isinstance(entry, dict):
                identities.append(json.dumps(entry, ensure_ascii=False, sort_keys=True))
                continue
            identity = entry.get("id") or entry.get("link") or (
                entry.get("title"), entry.get("company"), entry.get("location")
            )
            identities.append(json.dumps(identity, ensure_ascii=False, sort_keys=True))
            link = entry.get("link")
            if not isinstance(link, str) or urlparse(link).scheme != "https":
                continue
            title = entry.get("title")
            company = entry.get("company") or "Nie podano"
            job_location = entry.get("location") or location
            if not all(
                isinstance(value, str) and value.strip()
                for value in (title, company, job_location)
            ):
                continue
            jobs.append(
                RawJob(
                    title=title,
                    company=company,
                    city=job_location,
                    url=link,
                    description=str(entry.get("snippet") or ""),
                    source=str(entry.get("source") or "Jooble"),
                    salary_raw=str(entry["salary"]) if entry.get("salary") else None,
                )
            )

        fingerprint = hashlib.sha256(
            json.dumps(sorted(identities), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest() if identities else ""
        return JooblePage(jobs, len(entries), total_count, fingerprint)

    async def fetch_jobs(self) -> list[RawJob]:
        if not self.api_key:
            return []
        jobs: list[RawJob] = []
        try:
            for search in self.searches:
                jobs.extend((await self.fetch_page(search, 1)).jobs)
            return jobs
        finally:
            await self.close()
