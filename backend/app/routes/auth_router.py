from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.services.logger import app_logger
from app.config import settings
from app.types import SignupRequest, LoginRequest, UserInfoResponse
from app.services.auth_utils import create_session, require_auth, set_session_cookie
from app.services.auth_utils import (
  hash_password,
  verify_password,
  create_user_info_list,
)
from app.services.redis import cache_delete_session
from app.repositories.PostgresUserRepo import PostgresUserRepo, get_user_repo
from app.repositories.PostgresSessionRepo import PostgresSessionRepo, get_session_repo

auth_router = APIRouter()

# # -----------------------------------------------------------------------------
# Native Authentication Routes
# # -----------------------------------------------------------------------------


@auth_router.post("/api/auth/signup")
async def signup(
  signup_request: SignupRequest,
  postgres_user_repo: PostgresUserRepo = Depends(get_user_repo),
):
  """Endpoint for handling user signups

  Raises:
      HTTPException: Raises 400 if user with email already exists

  Returns:
      HTTP 201 Created on successful signup
  """

  user = await postgres_user_repo.get_user_by_email(signup_request.email)
  if user:
    app_logger.warning(
      f"Failed signup attempt since user with email '{signup_request.email}' already exists!"
    )
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="User with this email already exists.",
    )

  password_hash = hash_password(signup_request.password)
  await postgres_user_repo.create_user(
    signup_request.email,
    signup_request.full_name,
    password_hash,
  )
  app_logger.info(f"User {signup_request.email} was created successfully.")
  return status.HTTP_201_CREATED


@auth_router.post("/api/auth/login")
async def login(
  login_request: LoginRequest,
  response: Response,
  postgres_user_repo: PostgresUserRepo = Depends(get_user_repo),
  postgres_session_repo: PostgresSessionRepo = Depends(get_session_repo),
) -> UserInfoResponse:
  """Endpoint handling user logins

  Raises:
      HTTPException: Raises a 400 if email or password is incorrect
  """
  user = await postgres_user_repo.get_user_by_email(login_request.email)
  if not user:
    app_logger.warning(f"Login attempt with invalid email: {login_request.email}")
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST, detail="Email or password is incorrect!"
    )

  matched = verify_password(login_request.password, user["password_hash"])
  if not matched:
    app_logger.warning(f"Failed password attempt for user: {login_request.email}")
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST, detail="Email or password is incorrect!"
    )

  user_info: UserInfoResponse = create_user_info_list([user])[0]

  user_id = user_info["id"]
  user_email = user_info["email"]

  # Check if user already has a valid session (existing and non-expired)
  # Note: Can't really query Redis here, but honestly that's not that important since
  # logging in with an existing session is outside of the normal flow. However, we'll still
  # delete any potential cached session in redis.
  existing_session = await postgres_session_repo.get_session_by_user_id(user_id)
  if existing_session:
    await postgres_session_repo.delete_session_by_user_id(user_id)
    await cache_delete_session(existing_session["session_token"])
    app_logger.info(
      f"User {user_email} has a previous session (active/inactive). Destroying previous session."
    )

  # Else no existing session, create a new session in database and set cookie
  session_token = await create_session(user_id)
  set_session_cookie(response, session_token)
  app_logger.info(f"New session created for '{user_email}'!")
  return user_info


@auth_router.get("/api/auth/logout")
async def logout(
  request: Request,
  response: Response,
  postgres_session_repo: PostgresSessionRepo = Depends(get_session_repo),
):
  """Endpoint for handling user logout. Removes session from storage, removes cookies, etc. It'll return a HTTP 204 if no session cookie was found, otherwise an HTTP 200 Ok."""
  session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
  if not session_token:
    app_logger.info("No session cookie detected, no further action")
    return status.HTTP_204_NO_CONTENT

  response.delete_cookie(settings.SESSION_COOKIE_NAME)
  await postgres_session_repo.delete_session_by_token(session_token)
  await cache_delete_session(session_token)
  app_logger.info("Cookie detected, user logged out, and session deleted in storage")

  return status.HTTP_200_OK


@auth_router.get("/api/auth/verify")
async def verify(
  user_id: int = Depends(require_auth),
  postgres_user_repo: PostgresUserRepo = Depends(get_user_repo),
) -> UserInfoResponse:
  """Verifies whether a user is authenticated, if so we'll return the user's information back.

  Note: This is most useful for the frontend as you'd display this info on a dashboard, use it for personalization.
  This may change over time depending on what data the app supports.
  However again we won't return sensitive info like passsword_hash and other stuff.

  Raises:
      HTTPException: A 404 in the where the user somehow had a session but the user themselves wasn't stored in the database.
  """

  # At this point user has a valid session, let's return user information for the client side
  user = await postgres_user_repo.get_user_by_id(user_id)
  if not user:
    app_logger.warning(
      "User was authenticated (session found), but user themselves didn't exist in db"
    )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
  return create_user_info_list([user])[0]
