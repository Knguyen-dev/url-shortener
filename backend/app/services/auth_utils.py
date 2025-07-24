from typing import Dict, Optional
from datetime import datetime
import asyncpg
from fastapi import HTTPException, Request, Response, status
from app.config import settings
from app.services.postgres import connect_db
from app.services.logger import app_logger
import secrets

# TODO: Should use logging here to see what's happening

# # -----------------------------
# Session Create Utilities
# # -----------------------------
def generate_session_token() -> str:
  """Create a cryptographically secure session token (32 bytes)"""
  return secrets.token.urlsafe(32)

async def create_session(user_id: int, db_conn=None) -> str:  
  """Creates a session"""
  session_token = generate_session_token()
  await db_conn.execute(
    """INSERT INTO sessions (user_id, session_token, expires_at) VALUES ($1, $2, $3)""",
    user_id,
    session_token,
    datetime.now(datetime.timezone.utc) + settings.SESSION_LIFETIME
    )
  return session_token

def set_session_cookie(response: Response, session_token: str):
  """Sets the session cookie in the response"""
  response.set_cookie(
    key=settings.SESSION_COOKIE_NAME,
    value=session_token,
    max_age=int(settings.SESSION_LIFETIME.total_seconds()),
    httponly=True,
    secure=settings.COOKIE_SECURE,
    samesite="lax",
    domain=None,
    path="/"
  )

  # Ensure cookie is not cached by the browser; another layer of security against local access
  # As a result, cookies are destroyed after the browser is closed.
  response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
  response.headers['Pragma'] = 'no-cache'
  response.headers['Expires'] = '0'

# # ------------------------------
# Session Management Primitive Utilities
# # ------------------------------
async def get_session_by_token(db_conn: asyncpg.Connection, session_token: str) -> Optional[Dict[any, any]]:
  """Gets a session object with a session token"""
  return await db_conn.execute(
    "SELECT * FROM sessions WHERE session_token = ?",
    session_token
  )

def is_session_expired(session: Dict[any, any]) -> bool:
  """Checks if a session is expired"""
  current_time = datetime.now()
  return current_time > session["expired_at"]

async def cleanup_expired_session(db_conn: asyncpg.Connection, session_token: str) -> None:
  """Remove expired session from database."""
  await db_conn.execute(
    "DELETE FROM sessions WHERE session_token = ?",
    session_token
  )

async def validate_session(db_conn: asyncpg.Connection, session_token: str) -> Optional[Dict[any, any]]:
  """Validates session and returns session data if valid. Handles database cleanup if session is expired."""
  session = await get_session_by_token(db_conn, session_token)
  if session is None:
    return None
  
  if is_session_expired(session):
    await cleanup_expired_session(db_conn, session_token)
    return None

  return session

# # ---------------------------------
# Auth utilities
# # ---------------------------------
def get_session_token_from_request(request: Request) -> Optional[str]:
  """Extracts session token from request cookie"""
  return request.cookies.get(settings.SESSION_COOKIE_NAME)

def clear_session_cookie(response: Response) -> None:
  """Clears session cookie from response"""
  response.delete_cookie(settings.SESSION_COOKIE_NAME)

async def get_current_session(request: Request, response: Response, db_conn: asyncpg.Connection) -> Optional[Dict]:
  """Get current valid session, handling cleanup if expired."""
  session_token = get_session_token_from_request(request)
  if not session_token:
    return None
  session = await validate_session(db_conn, session_token)
  if session is None:
    clear_session_cookie(response)
  return session

async def get_current_user_id(request: Request, response: Response, db_conn: asyncpg.Connection) -> Optional[str]:
  """Gets current user ID from valid session"""
  session = await get_current_session(request, response, db_conn)
  return session["user_id"] if session else None

async def get_current_user(request: Request, response: Response, db_conn: asyncpg.Connection) -> Optional[Dict[any, any]]:
  """Gets current user from valid session"""
  session = await get_current_session(request, response, db_conn)
  if session is None:
    return None
  user = await db_conn.execute(
    "SELECT * FROM users WHERE id = ?",
    session["user_id"]
  )
  return user

# # ------------------------------
# Authentication Middleware
# # ------------------------------
async def authenticate_request(request: Request, response: Response, db_conn: asyncpg.Connection) -> None:
  """Middleware to authenticate request, attaches user info, and returns user id."""
  session_token = await get_session_token_from_request(request)
  if not session_token:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="No session token provided"
    )
  
  session = await validate_session(db_conn, session_token)
  if session is None:
    clear_session_cookie(response)
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid or expired session"
    )
  
  # Attach session info to request state
  user_id = session["user_id"]
  request.state.session = session
  request.state.user_id = user_id
  return user_id
  
# # -------------------------
# Dependency Injection for protected routes
# # -------------------------
async def require_auth(request: Request, response: Response) -> str:
  """Dependency that ensures user is authenticated and returns user id"""
  db_conn = await connect_db()
  user_id = await authenticate_request(request, response, db_conn)
  return user_id

async def optional_auth(request: Request, response: Response) -> str:
  """Dependency for optional authentication, returns user_id or None."""
  try:
    return await require_auth(request, response)
  except HTTPException:
    return None

# Usage in routes:
# @app.get("/protected")
# async def protected_route(user_id: str = Depends(require_auth)):
#     return {"user_id": user_id}
#
# @app.get("/optional-auth")
# async def optional_route(user_id: Optional[str] = Depends(get_optional_auth)):
#     if user_id:
#         return {"authenticated": True, "user_id": user_id}
#     return {"authenticated": False}