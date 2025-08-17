from datetime import datetime, timedelta
import asyncpg
from app.services.postgres import get_postgres_pool


class PostgresSessionRepo:
  def __init__(self, pool: asyncpg.Pool):
    self.pool = pool

  async def create_session(self, user_id: int, session_token: str, created_at: datetime, last_active_at: datetime):
    """Creates a session in the database"""
    async with self.pool.acquire() as conn:
      return await conn.execute(
        """INSERT INTO sessions (user_id, session_token, created_at, last_active_at) VALUES ($1, $2, $3, $4)""",
        user_id,
        session_token,
        created_at,
        last_active_at
      )

  async def update_session_last_active_by_user_id(
    self, last_active_at: timedelta, user_id: int
  ):
    """Updates when a session was last active based for a given user"""
    async with self.pool.acquire() as conn:
      return await conn.execute(
        """UPDATE sessions SET last_active_at = $1 WHERE user_id = $2""",
        last_active_at,
        user_id,
      )

  async def get_session_by_user_id(self, user_id: int):
    """Returns a record of a session from the database"""
    async with self.pool.acquire() as conn:
      return await conn.fetchrow("SELECT * FROM sessions WHERE user_id = $1", user_id)

  async def delete_session_by_user_id(self, user_id: int):
    """Deletes a session in the database"""
    async with self.pool.acquire() as conn:
      return await conn.execute("DELETE FROM sessions WHERE user_id = $1", user_id)

  async def get_session_by_token(self, session_token: str):
    """Fetches a session record in the database via its session token"""
    async with self.pool.acquire() as conn:
      return await conn.fetchrow(
        "SELECT * FROM sessions WHERE session_token = $1", session_token
      )

  async def delete_session_by_token(self, session_token: str):
    """Deletes a session in the database via its session token"""
    async with self.pool.acquire() as conn:
      return await conn.execute(
        "DELETE FROM sessions WHERE session_token = $1", session_token
      )


def get_session_repo() -> PostgresSessionRepo:
  pool = get_postgres_pool()
  return PostgresSessionRepo(pool)
