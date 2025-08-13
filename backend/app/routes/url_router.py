from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from app.services.logger import app_logger
from app.types import CreateUrlRequest
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from app.services.redis import cache_increment_url_click, cache_get_url_click, cache_delete_url_click
from app.services.auth_utils import require_auth, hash_url_password, verify_url_password
from app.types import UrlPasswordRequest, UpdateUrlRequest
from app.services.backhalf_alias import AliasGenerator, get_alias_generator
from app.repositories.CassandraUrlRepo import get_cassandra_url_repo, CassandraUrlRepo
from app.repositories.CassandraClickRepo import get_cassandra_click_repo, CassandraClickRepo
from app.repositories.CassandraUrlByUserRepo import get_cassandra_url_by_user_repo, CassandraUrlByUserRepo

url_router = APIRouter()

@url_router.get("/{backhalf_alias}")
async def redirect_url(
   backhalf_alias: str, 
   cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo), 
   cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo)):
  """Handle redirecting the short urls we generate to the original urls"""
  existing_url = fetch_url_and_availability(backhalf_alias, cassandra_url_repo)
  if existing_url["password_hash"]:
    return { "password_required": True }  
  update_clicks_and_redirect(backhalf_alias, existing_url['original_url'], cassandra_click_repo)

@url_router.post("/verify-password/{backhalf_alias}")
async def url_verify_password(
   backhalf_alias: str, 
   password_request: UrlPasswordRequest, 
   cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo), 
   cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo)):
  """Handles authentication and redirects for password-protected urls"""

  existing_url = fetch_url_and_availability(backhalf_alias, cassandra_url_repo)
  stored_hash = existing_url['password_hash']
  if not stored_hash:
    raise HTTPException(
       status_code=status.HTTP_400_BAD_REQUEST,
       detail="URL isn't password protected. Please use the redirect endpoint!"
    )
   
  if not verify_url_password(password_request.password, stored_hash):
    raise HTTPException(
       status_code=status.HTTP_401_UNAUTHORIZED,
       detail="Incorrect password"
    )
  
  update_clicks_and_redirect(backhalf_alias, existing_url['original_url'], cassandra_click_repo)
  
@url_router.post("/api/urls")
async def create_url(
   create_url_request: CreateUrlRequest, 
   user_id: int = Depends(require_auth), 
   alias_generator: AliasGenerator = Depends(get_alias_generator),
   cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo), 
   cassandra_url_by_user_repo: CassandraUrlByUserRepo = Depends(get_cassandra_url_by_user_repo),
   cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo)
   ):
  """Handles when an authenticated user wants to create a short url"""

  is_valid, message = is_valid_url(create_url_request.original_url)
  if not is_valid:
     app_logger.warning(f"URL invalid: '{message}' with url '{create_url_request.original_url}'.")
     return HTTPException(
        status=status.HTTP_400_BAD_REQUEST,
        message=message
      )
  
  password_hash = None
  if create_url_request.password:
    app_logger.info(f"Generating URL password hash!")
    password_hash = hash_url_password(create_url_request.password)
  created_at = datetime.now(timezone.utc)

  backhalf_alias = alias_generator.generate_backhalf_alias()
  cassandra_url_repo.create_url(
     backhalf_alias,
     user_id,
     create_url_request.original_url,
     password_hash,
     create_url_request.is_active
  )
  cassandra_url_by_user_repo.create_url(
    user_id,
    backhalf_alias,
    create_url_request.original_url,
    create_url_request.is_active,
    create_url_request.title,
    created_at
  )
  cassandra_click_repo.create_clicks(backhalf_alias, 0)

  # Return the URL like it's from the main urls table; omit password hash though
  return {
    "backhalf_alias": backhalf_alias,
    "user_id": user_id,
    "original_url": create_url_request.original_url,
    "is_active": create_url_request.is_active
  }

@url_router.get("/api/urls/{backhalf_alias}")
async def get_url(
  backhalf_alias: str, 
  user_id: str = Depends(require_auth),
  cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo), 
  cassandra_url_by_user_repo: CassandraUrlByUserRepo = Depends(get_cassandra_url_by_user_repo),
  cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo)):
    """Gets all the info related to a url.
    Note: Endpoint is intended for development purposes and checking all the collective information
    for a url to ensure all the database interactions are working.
    """
    existing_url = cassandra_url_repo.get_url_by_alias(backhalf_alias)
    if not existing_url:
      raise HTTPException(
         status_code=status.HTTP_404_NOT_FOUND,
         detail="Url not found"
      )
    if existing_url["user_id"] != user_id:
      app_logger.warning(f"User ID '{user_id}' unauthorized to delete url from userID '{existing_url['user_id']}'")
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authorized to delete this url"
      )
    url_by_user = cassandra_url_by_user_repo.get_single_url(user_id, backhalf_alias)
    total_clicks = cassandra_click_repo.get_total_clicks(backhalf_alias)
    return {
       "url": existing_url,
       "url_by_user": url_by_user,
       "total_clicks": total_clicks
    }

@url_router.delete("/api/urls/{backhalf_alias}")
async def delete_url(
   backhalf_alias: str, 
   user_id: str = Depends(require_auth),
   cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo), 
   cassandra_url_by_user_repo: CassandraUrlByUserRepo = Depends(get_cassandra_url_by_user_repo),
   cassandra_click_repo: CassandraClickRepo = Depends(get_cassandra_click_repo)
  ):
  """Handles deleting a url given it's backhalf alias"""
  existing_url = cassandra_url_repo.get_url_by_alias(backhalf_alias)
  if not existing_url:
    raise HTTPException(
       status_code=status.HTTP_404_NOT_FOUND,
       detail="Url not found"
    )
  
  if existing_url["user_id"] != user_id:
    app_logger.warning(f"User ID '{user_id}' unauthorized to delete url from userID '{existing_url['user_id']}'")
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Not authorized to delete this url"
    )
  
  cassandra_url_repo.delete_url_by_alias(backhalf_alias)
  cassandra_url_by_user_repo.delete_single_url(user_id, backhalf_alias)
  cassandra_click_repo.delete_clicks(backhalf_alias)

  return {
     "message": f"Url with backhalf alias {backhalf_alias} was deleted!"
  }

@url_router.patch("/api/urls/{backhalf_alias}")
async def update_url(
  backhalf_alias: str, 
  update_url_request: UpdateUrlRequest, 
  user_id: str = Depends(require_auth),
  cassandra_url_repo: CassandraUrlRepo = Depends(get_cassandra_url_repo), 
  cassandra_url_by_user_repo: CassandraUrlByUserRepo = Depends(get_cassandra_url_by_user_repo),
):
  """Endpoint for updating an existing url"""
  existing_url = cassandra_url_repo.get_url_by_alias(backhalf_alias)
  if not existing_url:
    raise HTTPException(
       status_code=status.HTTP_404_NOT_FOUND,
       detail="Url not found"
    )
  
  if existing_url["user_id"] != user_id:
    app_logger.warning(f"UserID '{user_id}' unauthorized to update url from userID '{existing_url['user_id']}'")
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Not authorized to update this url"
    )

  try:
    password_hash = None
    if update_url_request.password:
      password_hash = hash_url_password(update_url_request.password)
    
    # Update the main and user-url table
    cassandra_url_repo.update_url_by_alias(
      update_url_request.is_active,  
      password_hash,
      backhalf_alias   
    )    
    cassandra_url_by_user_repo.update_url(
       update_url_request.is_active,
       update_url_request.title,
       user_id,
       backhalf_alias
    )

    return {
       "message": f"Updated URL '{backhalf_alias}'!"
    }
  except Exception as e:
     app_logger.error(f"Error updating URL: {str(e)}")
     raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Error updating URL. Internal error, try again later."
     )

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
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Basic regex check
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
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

def fetch_url_and_availability(backhalf_alias: str, cassandra_url_repo: CassandraUrlRepo):
  """Returns URL and raises error if it's not available

  Raises:
      HTTPException: Url not found, a 404 error. 
      HTTPException: Url is marked as inactive.
  """
  existing_url = cassandra_url_repo.get_url_by_alias(backhalf_alias)
  if not existing_url:
    raise HTTPException(
       status_code=status.HTTP_404_NOT_FOUND,
       detail="Url not found"
    )
  
  if not existing_url["is_active"]:
     raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Redirect Denied. Url has been marked as inactive!"
     )
  return existing_url

def update_clicks_and_redirect(backhalf_alias: str, original_url, cassandra_click_repo: CassandraClickRepo):
  """Updates the click count and redirects the client for an existing url
  
  Args:
      backhalf_alias (str): Assumed to be associated with an existing URL.
      original_url (str): The url that we're redirecting to.

  Note: Please ensure that backhalf_alias is associated with an existing URL.
  """
  
  click_count = cache_get_url_click(backhalf_alias)
  if click_count >= 5:
    cache_delete_url_click(backhalf_alias)
    cassandra_click_repo.update_url_clicks(backhalf_alias, click_count)
    app_logger.info(f"Flushing {click_count} url clicks from Redis to database.")
  else: 
    # Else it isn't above the threshold so increase the click in redis.s
    cache_increment_url_click(backhalf_alias)

  return RedirectResponse(
     url=original_url,
     status_code=302 # Return 302 to prevent browser level caching.
  ) 