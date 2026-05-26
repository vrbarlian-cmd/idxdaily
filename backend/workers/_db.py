"""
Async PostgreSQL connection helper using asyncpg.

DATABASE_URL must be a Postgres DSN (sslmode=require is supported for Neon).
Load .env before importing this module.
"""
import asyncpg
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Populated by each worker after dotenv load
DATABASE_URL: str = ""


def _url() -> str:
    url = os.environ.get("DATABASE_URL", DATABASE_URL)
    if not url or url.startswith("file:"):
        raise RuntimeError(
            "DATABASE_URL is not set or still points to a SQLite file. "
            "Set a Postgres DSN in .env."
        )
    return url


async def get_conn() -> asyncpg.Connection:
    """Open a single asyncpg connection."""
    return await asyncpg.connect(_url())


async def get_pool(min_size: int = 1, max_size: int = 5) -> asyncpg.Pool:
    """Create a connection pool (preferred for long-running services)."""
    return await asyncpg.create_pool(_url(), min_size=min_size, max_size=max_size)
