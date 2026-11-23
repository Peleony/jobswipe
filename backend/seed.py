import asyncio
import json

from app.config import load_local_env
from app.database import JobRepository, configured_database_path
from app.main import RefreshService, _configured_providers


async def seed() -> None:
    load_local_env()
    repository = JobRepository(configured_database_path())
    repository.initialize()
    result = await RefreshService(repository, _configured_providers()).refresh()
    print(json.dumps({**result, "unique_jobs": repository.count()}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(seed())
