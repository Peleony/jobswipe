import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from .models import CleanJob


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = BACKEND_DIR / "data" / "jobswipe.db"


def configured_database_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    if not configured:
        return DEFAULT_DATABASE_PATH
    path = Path(configured).expanduser()
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


class JobRepository:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else configured_database_path()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_hash TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    city TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source TEXT NOT NULL,
                    industries_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    salary_json TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_state (
                    provider_name TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_leases (
                    provider_name TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    lease_until REAL NOT NULL
                )
                """
            )

    def upsert_many(self, jobs: Iterable[CleanJob]) -> tuple[int, int]:
        records = list(jobs)
        if not records:
            return 0, 0

        with self._connection() as connection:
            return self._upsert_many(connection, records)

    @staticmethod
    def _upsert_many(connection: sqlite3.Connection, records: list[CleanJob]) -> tuple[int, int]:
        hashes = [job.hash for job in records]
        existing: set[str] = set()
        for offset in range(0, len(hashes), 900):
            chunk = hashes[offset : offset + 900]
            placeholders = ",".join("?" for _ in chunk)
            rows = connection.execute(
                f"SELECT job_hash FROM jobs WHERE job_hash IN ({placeholders})", chunk
            )
            existing.update(row["job_hash"] for row in rows)

        connection.executemany(
            """
            INSERT INTO jobs (
                job_hash, title, company, city, url, description, summary, source,
                industries_json, tags_json, salary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_hash) DO UPDATE SET
                title = excluded.title,
                company = excluded.company,
                city = excluded.city,
                url = excluded.url,
                description = excluded.description,
                summary = excluded.summary,
                source = excluded.source,
                industries_json = excluded.industries_json,
                tags_json = excluded.tags_json,
                salary_json = excluded.salary_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            [
                (
                    job.hash,
                    job.title,
                    job.company,
                    job.city,
                    job.url,
                    job.description,
                    job.summary,
                    job.source,
                    json.dumps(job.industries, ensure_ascii=False),
                    json.dumps(job.tags, ensure_ascii=False),
                    json.dumps(job.salary.model_dump(mode="json"), ensure_ascii=False)
                    if job.salary
                    else None,
                )
                for job in records
            ],
        )
        inserted = sum(job.hash not in existing for job in records)
        return inserted, len(records) - inserted

    def load_provider_state(self, provider_name: str) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT state_json FROM provider_state WHERE provider_name = ?", (provider_name,)
            ).fetchone()
        return json.loads(row["state_json"]) if row else None

    def save_provider_state(self, provider_name: str, state: dict[str, object]) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO provider_state (provider_name, state_json) VALUES (?, ?)
                ON CONFLICT(provider_name) DO UPDATE SET state_json = excluded.state_json
                """,
                (provider_name, json.dumps(state, ensure_ascii=False)),
            )

    def commit_provider_page(
        self, provider_name: str, state: dict[str, object], jobs: Iterable[CleanJob]
    ) -> tuple[int, int]:
        records = list(jobs)
        with self._connection() as connection:
            counts = self._upsert_many(connection, records) if records else (0, 0)
            connection.execute(
                """
                INSERT INTO provider_state (provider_name, state_json) VALUES (?, ?)
                ON CONFLICT(provider_name) DO UPDATE SET state_json = excluded.state_json
                """,
                (provider_name, json.dumps(state, ensure_ascii=False)),
            )
        return counts

    def acquire_refresh_lease(
        self, provider_name: str, owner: str, lease_seconds: int = 120
    ) -> bool:
        now = time.time()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT owner, lease_until FROM refresh_leases WHERE provider_name = ?",
                (provider_name,),
            ).fetchone()
            if row and row["owner"] != owner and row["lease_until"] > now:
                return False
            connection.execute(
                """
                INSERT INTO refresh_leases (provider_name, owner, lease_until)
                VALUES (?, ?, ?)
                ON CONFLICT(provider_name) DO UPDATE SET owner = excluded.owner,
                    lease_until = excluded.lease_until
                """,
                (provider_name, owner, now + lease_seconds),
            )
        return True

    def renew_refresh_lease(
        self, provider_name: str, owner: str, lease_seconds: int = 120
    ) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE refresh_leases SET lease_until = ? WHERE provider_name = ? AND owner = ?",
                (time.time() + lease_seconds, provider_name, owner),
            )
        return cursor.rowcount == 1

    def release_refresh_lease(self, provider_name: str, owner: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM refresh_leases WHERE provider_name = ? AND owner = ?",
                (provider_name, owner),
            )

    def list_jobs(
        self,
        *,
        city: str | None = None,
        blocked_tags: list[str] | None = None,
        blocked_industries: list[str] | None = None,
        exclude_hashes: list[str] | None = None,
        require_salary: bool = False,
        limit: int = 50,
    ) -> list[CleanJob]:
        conditions: list[str] = []
        values: list[str | int] = []
        for column, blocked in (
            ("tags_json", blocked_tags or []),
            ("industries_json", blocked_industries or []),
        ):
            if blocked:
                placeholders = ",".join("?" for _ in blocked)
                conditions.append(
                    f"NOT EXISTS (SELECT 1 FROM json_each(jobs.{column}) "
                    f"WHERE json_each.value IN ({placeholders}))"
                )
                values.extend(blocked)
        if exclude_hashes:
            conditions.append("job_hash NOT IN (SELECT value FROM json_each(?))")
            values.append(json.dumps(exclude_hashes))
        if require_salary:
            conditions.append("salary_json IS NOT NULL")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM jobs {where_clause} ORDER BY updated_at DESC, job_hash"
        if not city:
            query += " LIMIT ?"
            values.append(limit)
        with self._connection() as connection:
            rows = connection.execute(query, values).fetchall()

        jobs = [self._to_job(row) for row in rows]
        if city:
            from .cleaner import normalize_text

            needle = normalize_text(city)
            jobs = [job for job in jobs if needle in normalize_text(job.city)]
        return jobs[:limit]

    def delete_by_source(self, source: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM jobs WHERE source = ?", (source,))

    def count(self) -> int:
        with self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM jobs").fetchone()
        return int(row["total"])

    @staticmethod
    def _to_job(row: sqlite3.Row) -> CleanJob:
        return CleanJob(
            hash=row["job_hash"],
            title=row["title"],
            company=row["company"],
            city=row["city"],
            url=row["url"],
            description=row["description"],
            summary=row["summary"],
            source=row["source"],
            industries=json.loads(row["industries_json"]),
            tags=json.loads(row["tags_json"]),
            salary=json.loads(row["salary_json"]) if row["salary_json"] else None,
        )
