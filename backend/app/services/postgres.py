from typing import Optional
import asyncpg
import asyncio
from pathlib import Path
from app.config import settings
from .logger import app_logger

_postgres_pool: Optional[asyncpg.Pool] = None


def get_postgres_pool() -> asyncpg.Pool:
  """Returns a reference to the postgres connection pool"""
  if _postgres_pool is None:
    raise RuntimeError("Postgres Pool wasn't initialized")
  return _postgres_pool


async def init_postgres():
  """
  Setup Postgres connection pool with retry logic

  Args:
      max_retries: Maximum number of connection attempts
      retry_delay: Delay between retry attempts in seconds
  """

  global _postgres_pool

  _postgres_pool = None
  max_retries = 3
  retry_delay = 3  # try every 3 seconds

  for attempt in range(1, max_retries + 1):
    try:
      app_logger.info(
        f"Attempting to connect to Postgres (attempt {attempt}/{max_retries})"
      )

      _postgres_pool = await asyncpg.create_pool(
        settings.POSTGRES_URL, min_size=5, max_size=20, command_timeout=60
      )

      # Test the connection
      async with _postgres_pool.acquire() as conn:
        await conn.fetchval("SELECT 1")

      app_logger.info("Postgres connection established!")

      # Run migrations
      migration_path = Path(__file__).parent / "migrations"
      if not migration_path.is_dir():
        app_logger.info(
          f"Migration directory not found: {migration_path}. Skipping the running of migrations!"
        )
        return _postgres_pool

      sql_files = sorted(migration_path.glob("*.sql"))
      if not sql_files:
        app_logger.info(
          "No SQL migration files found. Skipping the running of migrations!"
        )
        return _postgres_pool

      async with _postgres_pool.acquire() as conn:
        for file in sql_files:
          sql = file.read_text()
          app_logger.info(f"Running migration: {file.name}")
          await conn.execute(sql)
      app_logger.info("Postgres migrations were run successfully!")

      # IMPORTANT: Return after establishing connection
      return

    except asyncpg.PostgresConnectionError as e:
      app_logger.warning(f"Postgres connection attempt {attempt} failed: {e}")
      if attempt == max_retries:
        app_logger.error(
          f"Failed to connect to Postgres after {max_retries} attempts: {e}"
        )
        raise RuntimeError(
          f"Postgres connection failed after {max_retries} attempts: {e}"
        ) from e

      # Close the pool if it was created but connection test failed
      if _postgres_pool:
        await _postgres_pool.close()
        _postgres_pool = None

      app_logger.info(f"Retrying in {retry_delay} seconds...")
      await asyncio.sleep(retry_delay)

    except Exception as e:
      app_logger.error(
        f"Unexpected error connecting to Postgres (attempt {attempt}): {e}"
      )
      if attempt == max_retries:
        # Close the pool if it was created
        if _postgres_pool:
          await _postgres_pool.close()
        raise RuntimeError(
          f"Postgres connection failed after {max_retries} attempts: {e}"
        ) from e

      # Close the pool if it was created but something else failed
      if _postgres_pool:
        await _postgres_pool.close()
        _postgres_pool = None

      app_logger.info(f"Retrying in {retry_delay} seconds...")
      await asyncio.sleep(retry_delay)

  # This should never be reached, but just in case
  raise RuntimeError("Postgres connection failed: Maximum retries exceeded")


async def cleanup_postgres():
  """Closes the connection pool on shutdown."""
  global _postgres_pool
  if _postgres_pool:
    await _postgres_pool.close()
    app_logger.info("Postgres connection closed and cleaned up!")
