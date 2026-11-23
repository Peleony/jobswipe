import os
from urllib.parse import urlparse

import httpx

from ..models import RawJob
from .base import BaseJobProvider, ProviderError


class JoobleProvider(BaseJobProvider):
    name = "jooble"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 12,
        client: httpx.AsyncClient | None = None,
    ):
        self.api_key = (api_key if api_key is not None else os.getenv("JOOBLE_API_KEY", "")).strip()
        self.base_url = (
            base_url or os.getenv("JOOBLE_API_BASE_URL", "https://jooble.org/api")
        ).rstrip("/")
        self.timeout = timeout
        self.client = client

    async def fetch_jobs(self) -> list[RawJob]:
        if not self.api_key:
            return []

        if self.client is not None:
            return await self._fetch_with_client(self.client)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._fetch_with_client(client)

    async def _fetch_with_client(self, client: httpx.AsyncClient) -> list[RawJob]:
        jobs: list[RawJob] = []
        for city in ("Kraków", "Warszawa", "Wrocław"):
            try:
                response = await client.post(
                    f"{self.base_url}/{self.api_key}",
                    json={
                        "keywords": "praca dla studenta, bez doświadczenia, praca dorywcza",
                        "location": city,
                        "page": "1",
                        "ResultOnPage": 20,
                        "companysearch": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPStatusError as exc:
                raise ProviderError(f"Jooble returned HTTP {exc.response.status_code}") from None
            except (httpx.HTTPError, ValueError):
                raise ProviderError("Jooble request or response failed") from None

            entries = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(entries, list):
                raise ProviderError("Jooble returned an unexpected response")
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                link = entry.get("link")
                if not isinstance(link, str) or urlparse(link).scheme != "https":
                    continue
                title = entry.get("title")
                company = entry.get("company") or "Nie podano"
                location = entry.get("location") or city
                if not all(isinstance(value, str) and value.strip() for value in (title, company, location)):
                    continue
                jobs.append(
                    RawJob(
                        title=title,
                        company=company,
                        city=location,
                        url=link,
                        description=str(entry.get("snippet") or ""),
                        source=str(entry.get("source") or "Jooble"),
                        salary_raw=str(entry["salary"]) if entry.get("salary") else None,
                    )
                )
        return jobs
