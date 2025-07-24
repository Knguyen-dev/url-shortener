from fastapi import APIRouter, HTTPException, Request, Response, status
from argon2 import PasswordHasher
from app.services.logger import app_logger
from app.services.postgres import connect_db
from app.config import settings
from app.types import SignupRequest, LoginRequest
from app.services.auth_utils import create_session, set_session_cookie

router = APIRouter()
password_hasher = PasswordHasher() # TODO: Is this fine to be global?

# # -----------------------------------------------------------------------------
# Native Authentication Routes
# # -----------------------------------------------------------------------------

@router.post("/auth/signup")
async def signup(signup_request: SignupRequest):
  """Endpoint for handling native user signup"""
  db = await connect_db()
  user = await db.fetchrow("SELECT * FROM users WHERE email = $1", signup_request.email)
  if user:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="User with this email already exists."
    )
  
  password_hash = password_hasher.hash(signup_request.password)
  await db.execute(
    """INSERT INTO users (email, password_hash) VALUES ($1, $2, $3)""",
    signup_request.email,
    password_hash,
  )
  await db.close()
  app_logger.info(f"User {signup_request.email} was created successfully.")
  return status.HTTP_201_CREATED

@router.post("/auth/login")
async def login(login_request: LoginRequest, response: Response):
  """Endpoint for handling native user login
  
  
  Note: This endpoint has two main responsibillities:
    1. Setting a cookie in the response, used to authenticate following subsequent backend requests (proof of auth).
    2. Sending back user info about the currently logged in user for display purposes and it can also act as client-side auth.
  """  
  db_conn = await connect_db()
  user = await db_conn.fetchrow("SELECT * FROM users WHERE email = $1", login_request.email)
  if not user:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Username or password is incorrect!"
    )
  
  matched = password_hasher.verify(user["password_hash"], login_request.password)
  if not matched:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Username or password is incorrect!"
    )
  
  user_info = {
    "id": user['id'],
    "email": user['email'],
    "is_admin": user['is_admin'],
  }

  # Check if user already has an active (not expired) session
  existing_session = await db_conn.fetchrow(
    """SELECT * FROM sessions WHERE user_id = $1 AND expires_at > NOW()"""
  )
  
  # Note: A normal user would not be able to access this endpoint (from client side) if they were already logged in.
  # This is a safeguard to ensure we're not creating multiple session for the same user.
  if existing_session:
    app_logger.info(f"User {user_info['email']} already has an active session.")
    await db_conn.close()
    return user_info
  
  # Create session in database and set cookie
  session_token = await create_session(user["id"], db_conn)
  set_session_cookie(response, session_token)
  await db_conn.close()
  app_logger.info(f"User {user_info['email']} was logged in.")
  return user_info

@router.get("/auth/logout")
async def logout(request: Request, response: Response):
  """Endpoint for handling user logout"""
  session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
  response.delete_cookie(settings.SESSION_COOKIE_NAME)
  if session_token:
    db_conn = await connect_db()
    await db_conn.execute(
      """DELETE FROM sessions WHERE session_token = $1"""
      , session_token
    )
    await db_conn.close()
  app_logger.info("User logged out successfully.")
  return response