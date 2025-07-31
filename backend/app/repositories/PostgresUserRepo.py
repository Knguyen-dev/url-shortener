import asyncpg 
from app.services.postgres import get_postgres_pool

class PostgresUserRepo:
  # Uses asyncpg, so I guess each method should accept a db_conn: Connection
  # or just call connect_db internally to get things done.
  def __init__(self, pool: asyncpg.Pool):
    self.pool = pool

  # TODO: Verify that these work as well
  # Should verify that all of the repository classes are working as expected honestly.

  async def get_all_users(self):
    async with self.pool.acquire() as conn:
      return await conn.fetchrow("SELECT * FROM users")

  async def get_user_by_email(self, email: str):
    async with self.pool.acquire() as conn:
      result = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
      return result

  async def create_user(self, email: str, full_name, password_hash: str, is_admin: bool = False):
    async with self.pool.acquire() as conn:
      return await conn.execute(
        """INSERT INTO users (email, full_name, is_admin, password_hash) VALUES ($1, $2, $3, $4)""",
        email,
        full_name,
        is_admin,
        password_hash
      )

  async def get_user_by_id(self, user_id: str):
    async with self.pool.acquire() as conn:
      return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id) 
  
  async def delete_user_by_id(self, user_id: str):
    async with self.pool.acquire() as conn:
      return await conn.fetchrow("DELETE FROM users WHERE id = $1", user_id)

async def get_user_repo() -> PostgresUserRepo:
  pool = get_postgres_pool()
  return PostgresUserRepo(pool)