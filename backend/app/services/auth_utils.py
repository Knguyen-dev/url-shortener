from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import argon2
from fastapi import HTTPException, Request, Response, status
from app.config import settings
from app.services.logger import app_logger
import secrets
from argon2 import PasswordHasher
from app.repositories.PostgresSessionRepo import get_session_repo
from app.repositories.PostgresUserRepo import get_user_repo


# # --------------------------------------------------
# Password Creation and Verification Utilties
# # --------------------------------------------------
def hash_password(plaintext_password: str) -> str:
  """Hashes a plaintext password"""
  try:
    password_hasher = PasswordHasher() 
    return password_hasher.hash(plaintext_password)
  except Exception as e:
    app_logger.error(f"Failed to hash password: {str(e)}")
    raise

def verify_password(plaintext_password: str, password_hash: str) -> str:
  """Verifies a plaintext password and a password hash"""
  password_hasher = PasswordHasher()
  try:
    password_hasher.verify(password_hash, plaintext_password)
    return True
  except (
    argon2.exceptions.VerifyMismatchError,
    argon2.exceptions.VerificationError,
    argon2.exceptions.InvalidHashError
  ) as e:
    app_logger.debug(f"Password verification failed: {type(e).__name__}")
    return False
  except Exception as e:
    app_logger.error(f"Unexpected error during password verification: {str(e)}")
    return False  

# # --------------------------------------------------
# Session Create Utilities
# # --------------------------------------------------

async def create_session(user_id: str) -> str:  
  """Creates a session for a user in the database and returns the session token

  Args:
      user_id (str): Id of the user who we'll create the session for

  Returns:
      str: Session token
  """
  try:
    # Generate a cryptographically secure session token (32 bytes)
    session_token = secrets.token_urlsafe(32)
    postgres_session_repo = get_session_repo()
    await postgres_session_repo.create_session(user_id, session_token)
    return session_token
  except Exception as e:
    app_logger.error(f"Failed to create session for user {user_id}: {str(e)}")
    raise

def set_session_cookie(response: Response, session_token: str):
  """Sets the session cookie in the response"""
  try:
    response.set_cookie(
      key=settings.SESSION_COOKIE_NAME,
      value=session_token,
      max_age=int(settings.SESSION_ABSOLUTE_LIFETIME.total_seconds()),
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
  except Exception as e:
    app_logger.error(f"Failed to set session cookie: {str(e)}")
    raise

# # --------------------------------------------------
# Session Management Primitive Utilities
# # --------------------------------------------------
def check_session_expiration(session: Dict[any, any]) -> Tuple[bool, str]:
  """Checks if session is expired and returns reason

  Returns:
        Tuple[bool, str]: (is_expired, reason)
  """
  current_time = datetime.now(timezone.utc)
  
  expires_at = session["created_at"] + settings.SESSION_ABSOLUTE_LIFETIME 

  # If absolute timeout
  # NOTE: You'll probably never see this log in production since the cookie should 
  # delete at the time the session hits the absolute timeout. Unless someone tries to copy the 
  # cookie ID and reconstruct it, but even then, they'll hit this error.
  if current_time > expires_at:
    return True, "absolute"
  
  # if idle timeout; If elapsed time exceeds our idle timeout
  if current_time - session["last_active_at"] > settings.SESSION_IDLE_LIFETIME:
    return True, "idle"

  return False, "valid"

async def validate_session(session_token: str) -> Optional[Dict[any, any]]:
  """Validates session and returns session data if valid"""
  try:
    postgres_session_repo = get_session_repo()
    session = await postgres_session_repo.get_session_by_token(session_token)
    if session is None:
      return None  

    # If expired, remove from database, log reason, etc.
    is_expired, reason = check_session_expiration(session)
    if is_expired:
      user_id = session.get("user_id", "unknown user_id")
      app_logger.warning(f"Session expired ({reason}) for user: {user_id}")
      return None
    
    return session
  except Exception as e:
    app_logger.error(f"Error during session validation: {str(e)}")
    return None

# # --------------------------------------------------
# Authentication Middleware
# # --------------------------------------------------
async def authenticate_request(request: Request, response: Response) -> None:
  """Middleware to authenticate request, and returns user id. Handles deleting cookies and cleaning up
  database sessions for invalid/expired sessions.

  Raises:
      HTTPException: Raised when no session cookie is provided
      HTTPException: Raised when invalid for expired session
  """
  session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
  if not session_token:
    app_logger.warning("Authentication failed: No session token provided!")
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Authentication failed: No session token provided"
    )
  
  session = await validate_session(session_token)
  if session is None:
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    postgres_session_repo = get_session_repo()
    await postgres_session_repo.delete_session_by_token(session_token)

    app_logger.warning("Authentication failed: Invalid or expired session!")
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid or expired session"
    )
  
  user_id = session["user_id"]
  return user_id
  
# # --------------------------------------------------
# Dependency Injection for protected routes
# # --------------------------------------------------
async def require_auth(request: Request, response: Response) -> str:
  """Dependency that ensures user is authenticated and returns user id"""
  user_id = await authenticate_request(request, response)

  try:
    # At this point we have an authenticated request (valid). Update the last_time_active to now!
    current_time = current_time = datetime.now(timezone.utc)
    postgres_session_repo = get_session_repo()
    await postgres_session_repo.update_session_last_active_by_user_id(current_time, user_id)
  except Exception as e:
    # Don't really want to fail the request for this.
    app_logger.error(f"Failed to update last_active for user {user_id}: {str(e)}")
    
  return user_id

async def require_admin(request: Request, response: Response) -> str:
  """Dependency that ensures user is authenticated and an administrator"""
  user_id = await require_auth(request, response)
  try:
    postgres_user_repo = get_user_repo()
    user = await postgres_user_repo.get_user_by_id(user_id)
    if not user["is_admin"]:
      app_logger.warning(f"User {user_id} does not have admin privileges!")
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin privileges are needed to access this resource."
      )
    return user_id
  except HTTPException:
    raise # Re-raise HTTPException, which is auto-logged
  except Exception as e:
    app_logger.error(f"Error checking admin status for user {user_id}: {str(e)}")
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Error verying admin privileges"
    )
  
async def optional_auth(request: Request, response: Response) -> str:
  """Dependency for optional authentication, returns user_id or None."""
  try:
    user_id = await require_auth(request, response)
    return user_id
  except HTTPException:
    # Stops propagating HTTP errors from require_auth -> authenticate_request
    # This lets the authentication actually be optional
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