from abc import ABC, abstractmethod

from ..models import RawJob


class ProviderError(Exception):
    """A provider failure safe to report without credentials or request URLs."""


class BaseJobProvider(ABC):
    name = "provider"

    @abstractmethod
    async def fetch_jobs(self) -> list[RawJob]:
        raise NotImplementedError
