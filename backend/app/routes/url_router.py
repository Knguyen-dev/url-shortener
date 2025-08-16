from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from app.services.logger import app_logger
from app.types import CreateUrlRequest
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from app.services.redis import cache_increment_url_click, cache_delete_url_click
from app.services.auth_utils import require_auth, hash_url_password, verify_url_password
from app.types import UrlPasswordRequest, UpdateUrlRequest
from app.config import settings
from app.services.backhalf_alias import AliasGenerator, get_alias_generator
from app.repositories.CassandraUrlRepo import get_cassandra_url_repo, CassandraUrlRepo
from app.repositories.CassandraClickRepo import (
  get_cassandra_click_repo,
  CassandraClickRepo,
)
from app.repositories.CassandraUrlByUserRepo import (
  get_cassandra_url_by_user_repo,
  CassandraUrlByUserRepo,
)

url_router = APIRouter()


@url_router.get("/{backhalf_alias}")
async def redirect_url(
  backhalf_alias: str,
  cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo),
  cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo),
):
  """Handle redirecting the short urls we generate to the original urls"""
  existing_url = fetch_url_and_availability(backhalf_alias, cassandra_url_repo)

  if existing_url["password_hash"]:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      # Lets the client know to prompt the user for a password and use the verify-
      detail={"password_required": True},
    )

  return await update_clicks_and_redirect(
    backhalf_alias, existing_url["original_url"], cassandra_click_repo
  )


@url_router.post("/api/urls/verify-password/{backhalf_alias}")
async def url_verify_password(
  backhalf_alias: str,
  password_request: UrlPasswordRequest,
  cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo),
  cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo),
):
  """Handles authentication and redirects for password-protected urls"""

  existing_url = fetch_url_and_availability(backhalf_alias, cassandra_url_repo)
  stored_hash = existing_url["password_hash"]
  if not stored_hash:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="URL isn't password protected. Please use the redirect endpoint!",
    )

  if not verify_url_password(password_request.password, stored_hash):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
    )

  return await update_clicks_and_redirect(
    backhalf_alias, existing_url["original_url"], cassandra_click_repo
  )


@url_router.get("/api/urls/{backhalf_alias}")
async def get_url(
  backhalf_alias: str,
  user_id: str = Depends(require_auth),
  cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo),
  cassandra_url_by_user_repo: CassandraUrlByUserRepo = Depends(
    get_cassandra_url_by_user_repo
  ),
  cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo),
):
  """Gets all the info related to a url.
  Note: Endpoint is intended for development purposes and checking all the collective information
  for a url to ensure all the database interactions are working.
  """
  existing_url = cassandra_url_repo.get_url_by_alias(backhalf_alias)
  if not existing_url:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Url not found")
  if existing_url["user_id"] != user_id:
    app_logger.warning(
      f"User ID '{user_id}' unauthorized to delete url from userID '{existing_url['user_id']}'"
    )
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Not authorized to delete this url",
    )
  url_by_user = cassandra_url_by_user_repo.get_single_url(user_id, backhalf_alias)
  total_clicks = cassandra_click_repo.get_total_clicks(backhalf_alias)
  return {"url": existing_url, "url_by_user": url_by_user, "total_clicks": total_clicks}


@url_router.delete("/api/urls/{backhalf_alias}")
async def delete_url(
  backhalf_alias: str,
  user_id: str = Depends(require_auth),
  cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo),
  cassandra_url_by_user_repo: CassandraUrlByUserRepo = Depends(
    get_cassandra_url_by_user_repo
  ),
  cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo),
):
  """Handles deleting a url given it's backhalf alias"""
  try:
    existing_url = cassandra_url_repo.get_url_by_alias(backhalf_alias)
    if not existing_url:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Url not found")

    if existing_url["user_id"] != user_id:
      app_logger.warning(
        f"User ID '{user_id}' unauthorized to delete url from userID '{existing_url['user_id']}'"
      )
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authorized to delete this url",
      )

    cassandra_url_repo.delete_url_by_alias(backhalf_alias)
    app_logger.info("Deleted url in main table")
    cassandra_url_by_user_repo.delete_single_url(user_id, backhalf_alias)
    app_logger.info("Deleted url in secondary table")
    cassandra_click_repo.delete_clicks(backhalf_alias)
    app_logger.info("Deleted url in clicks table")
    return {"message": f"Url with backhalf alias {backhalf_alias} was deleted!"}
  except HTTPException as e:
    raise e
  except Exception as e:
    app_logger.warning(f"Error deleting url: {str(e)}")
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Error deleting the url. Please try again later",
    )


@url_router.patch("/api/urls/{backhalf_alias}")
async def update_url(
  backhalf_alias: str,
  update_url_request: UpdateUrlRequest,
  user_id: str = Depends(require_auth),
  cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo),
  cassandra_url_by_user_repo: CassandraUrlByUserRepo = Depends(
    get_cassandra_url_by_user_repo
  ),
):
  """Endpoint for updating an existing url"""
  try:
    existing_url = cassandra_url_by_user_repo.get_single_url(user_id, backhalf_alias)
    if not existing_url:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Url not found")

    if existing_url["user_id"] != user_id:
      app_logger.warning(
        f"UserID '{user_id}' unauthorized to update url from userID '{existing_url['user_id']}'"
      )
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authorized to update this url",
      )

    if update_url_request.password and update_url_request.is_remove_password:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Cannot set and remove password at the same time.",
      )

    """
    ----- Handle Password Updates -----
    1. By default, keep existing password hash
    2. If we're removing the password, set the hash to None
    3. Else if the user defined a password:
      - This means they want to set/change the field.
      - Create new password hash
    4. Else the client didn't want to remove the password (if it even exists) and they didn't change or set one.
      This means that the password_hash field doesn't need to be changed.

    Note: Essentially our url_by_user_id table is for fetching all url data to show to the 
    user dashboard. It has is_active and password fields but not the password_hash field 
    because I don't think it's necessary for the user to re-confirm an old password for a link
    that they're going to change the password for. 

    There are two clear solutions:
    1. Add the password_hash field to the url_by_user_id repo
    2. Update the logic below have a flag indicating whether we're going to update 
      the password field or not. Then if is_password_change is true, then we'd call
      cassandra_url_repo.update_url_by_alias(is_active, password_hash, backhalf_alias).

      However if is_password_change is false, that means there's no need to update the password_hash
      field on the main urls table, the only thing you'd have to update would be the is_active field.
      You'd just use a separate query cassandra_url_update_is_active(is_active). This removes the need
      to update your data schema logic to include the password_hash field in the url_by_user_id table 
      and it prevents the need to do an extra query on the main URL table just to get the original 
      password. 
    """
    is_password_changed = True
    if update_url_request.is_remove_password:
      password_hash = None
    elif update_url_request.password:
      if update_url_request.password != update_url_request.confirm_password:
        raise HTTPException(
          status_code=status.HTTP_400_BAD_REQUEST,
          detail="Password and confirm password don't match.",
        )
      password_hash = hash_url_password(update_url_request.password)
    else:
      is_password_changed = False

    # ----- Handle Other Optional Updates -----
    # Note: Use the new properties if defined, else default to existing ones
    is_active = (
      update_url_request.is_active
      if update_url_request.is_active is not None
      else existing_url.get("is_active")
    )
    title = (
      update_url_request.title
      if update_url_request.title is not None
      else existing_url.get("title")
    )

    # ----- Update Cassandra Tables --------
    if is_password_changed:
      cassandra_url_repo.update_url_by_alias(is_active, password_hash, backhalf_alias)
    else:
      # Now only need to update the 'is_active' field
      cassandra_url_repo.update_url_is_active(is_active, backhalf_alias)

    cassandra_url_by_user_repo.update_url(is_active, title, user_id, backhalf_alias)

    return {"message": f"Updated URL '{backhalf_alias}'!"}
  except HTTPException:
    raise
  except Exception as e:
    app_logger.error(f"Error updating URL: {str(e)}")
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Error updating URL. Internal error, try again later.",
    )


@url_router.post("/api/urls")
async def create_url(
  create_url_request: CreateUrlRequest,
  user_id: int = Depends(require_auth),
  alias_generator: AliasGenerator = Depends(get_alias_generator),
  cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo),
  cassandra_url_by_user_repo: CassandraUrlByUserRepo = Depends(
    get_cassandra_url_by_user_repo
  ),
  cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo),
):
  """Handles when an authenticated user wants to create a short url"""

  is_valid, message = is_valid_url(create_url_request.original_url)
  if not is_valid:
    app_logger.warning(
      f"URL invalid: '{message}' with url '{create_url_request.original_url}'."
    )
    return HTTPException(status=status.HTTP_400_BAD_REQUEST, message=message)

  password_hash = None
  if create_url_request.password:
    password_hash = hash_url_password(create_url_request.password)

  try:
    backhalf_alias = alias_generator.generate_backhalf_alias()
    cassandra_url_repo.create_url(
      backhalf_alias,
      user_id,
      create_url_request.original_url,
      password_hash,
      create_url_request.is_active,
    )

    cassandra_url_by_user_repo.create_url(
      user_id,
      backhalf_alias,
      create_url_request.original_url,
      create_url_request.is_active,
      create_url_request.title,
      datetime.now(timezone.utc),
    )
    cassandra_click_repo.update_url_clicks(backhalf_alias, 0)
    return {
      "backhalf_alias": backhalf_alias,
      "user_id": user_id,
      "original_url": create_url_request.original_url,
      "is_active": create_url_request.is_active,
    }
  except Exception as e:
    app_logger.error(f"Error creating a url: {str(e)}")
    raise HTTPException(
      detail="Internal Server Error. Please try again later",
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

  # Return the URL like it's from the main urls table; omit password hash though


# # ---------------------------------------------------
# Utility or service functions to help url routers
# # ---------------------------------------------------
def is_valid_url(url: str) -> tuple[bool, str]:
  """Basic URL validation - checks format only

  Returns a tuple containing whether the url is valid or not.
  If the url is valid, the string will be the original url.
  Else the url isn't valid, so we'll send back a string indicating
  the error message.
  """

  # Add protocol if missing
  if not url.startswith(("http://", "https://")):
    url = "https://" + url

  # Basic regex check
  url_pattern = re.compile(
    r"^https?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
  )

  if not url_pattern.match(url):
    return False, "Invalid URL format"

  # Parse URL
  try:
    parsed = urlparse(url)
    if not parsed.netloc:
      return False, "Missing domain"
    return True, url
  except Exception:
    return False, "Invalid URL"


def fetch_url_and_availability(
  backhalf_alias: str, cassandra_url_repo: CassandraUrlRepo
):
  """Returns URL and raises error if it's not available

  Raises:
      HTTPException: Url not found, a 404 error.
      HTTPException: Url is marked as inactive.
  """
  existing_url = cassandra_url_repo.get_url_by_alias(backhalf_alias)
  if not existing_url:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Url not found")

  if not existing_url["is_active"]:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Redirect Denied. Url has been marked as inactive!",
    )
  return existing_url


async def update_clicks_and_redirect(
  backhalf_alias: str, original_url, cassandra_click_repo: CassandraClickRepo
):
  """Updates the click count and returns a redirect object.

  Args:
      backhalf_alias (str): Assumed to be associated with an existing URL.
      original_url (str): The url that we're redirecting to.

  Note:
    - Please ensure that backhalf_alias is associated with an existing URL.
  """
  click_count = await cache_increment_url_click(backhalf_alias)
  if click_count >= settings.CLICK_THRESHOLD:
    await cache_delete_url_click(backhalf_alias)
    cassandra_click_repo.update_url_clicks(backhalf_alias, click_count)

  return RedirectResponse(
    url=original_url,
    status_code=302,  # Return 302 to prevent browser level caching.
  )
