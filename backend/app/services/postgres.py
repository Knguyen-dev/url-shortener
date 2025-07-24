from datetime import datetime
import asyncpg
from pathlib import Path
from asyncpg import Connection
from fastapi import Request, Response
from app.config import settings
from .logger import app_logger

async def connect_db() -> Connection:
  return await asyncpg.connect(settings.POSTGRES_URL)

async def init_postgres():
  """Connects to db and runs SQL migration files in the migrations/ directory at startup."""
  conn = await connect_db()
  app_logger.info("Database connection established!")
  migration_path = Path(__file__).parent / "migrations"
  if not migration_path.is_dir():
    app_logger.info(
      f"Migration directory not found: {migration_path}. Skipping the running of migrations!"
    )
    return

  sql_files = sorted(migration_path.glob("*.sql"))
  if not sql_files:
    app_logger.info("No SQL migration files found. Skipping the running of migrations!")
    return

  try:
    for file in sql_files:
      sql = file.read_text()
      app_logger.info(f"Running migration: {file.name}")
      await conn.execute(sql)
    await conn.close()
    app_logger.info("Database migrations were run successfully!")
  except asyncpg.PostgresConnectionError as e:
    app_logger.error(f"Failed to connect to database: {e}!")
    raise RuntimeError(f"Database connection failed: {e}") from e
  except Exception as e:
    app_logger.error(f"Unexpected error connecting to database: {e}")
    raise RuntimeError(f"Database connection failed: {e}") from e


# # -----------------------------------
# Helper function verify user session
# # -----------------------------------  
async def get_user_id_by_session(request: Request, response: Response):
  """Get a user based on their session cookie
  
  Note: Checks if valid session
  """
  session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
  if session_cookie is None:
    return None
  
  db_conn = await connect_db()
  session = await db_conn.execute(
    """SELECT * FROM sessions WHERE session_token = ?""", 
    session_cookie
  )

  # If session wasn't found OR is expired
  if session is None:
    return None
  
  # If current session is expired
  current_time = datetime.now()
  if current_time > session["expired_at"]:
    await db_conn.execute(
      """DELETE FROM sessions WHERE session_token = ?""", 
      session_cookie
    )
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return None
  

  # TODO: Feel like this function does too much. Should rename this 
  # or get advice on what direction to tkae this 

  # My motivation was to have a piece of middleware that protected routes that 
  # needed authentication. the middleware would check for the cookie, then for a valid session.
  # Right now it only returns the ID of the user, but in my improved iteration of this function
  # I'll just set a flag on whether I want the full user or not

  # Return the id of the user making the request.
  return session["id"]

