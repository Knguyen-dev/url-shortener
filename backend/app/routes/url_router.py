from fastapi import APIRouter, HTTPException, Request, Response, status
from app.services.logger import app_logger
from app.services.cassandra import cassandra_session
from app.types import CreateUrlRequest
import re
from urllib.parse import urlparse
from app.services.redis import cache_increment_url_click, cache_get_url_click, cache_delete_url_click



router = APIRouter()


@router.get("/{backhalf_alias}")
async def redirect_url(backhalf_alias: str):
  """Handle redirecting the short urls we generate to the original urls"""

  # Attempt to query for url via backhalf_alias
  existing_url = cassandra_session.execute("""
    SELECT * FROM url_by_backhalf_alias WHERE backhalf_alias = ?
    """,
    [backhalf_alias]
  )
  if not existing_url:
    raise HTTPException(
       status_code=status.HTTP_404_NOT_FOUND,
       detail="Url not found"
    )
  
  # Check click count and flush it if it's above a given threshold
  click_count = cache_get_url_click(backhalf_alias)
  if click_count >= 5:
    cache_delete_url_click(backhalf_alias)
    cassandra_session.execute(
      f"""UPDATE url_clicks_by_backhalf_alias SET total_clicks = total_clicks + ? WHERE backhalf_alias = ?""",
      [click_count, backhalf_alias]                            
    )
    pass 

  
     
    
   

  # If it exists then:
  # - Check click count in redis, if click count == 5 (or greater >=), flush
  # - Else, Increment click count in redis
  # - Return a redirect with a 302
  pass

@router.post("/api/urls")
async def create_url(create_url_request: CreateUrlRequest):
  '''
  1. Verify the authenticated user
  2. Provides the following information:
    - original_url
    - title
    - password_hash: if defined, then this means the user wants to password protect the link
      else not defined, then it's not password protected so it'd be nulled by cassandra
  3. Create the url, populate our three tables
  4. Return response that resource was created.
  '''

  is_valid, message = is_valid_url(create_url_request.original_url)
  if not is_valid:
     return HTTPException(
        status=status.HTTP_400_BAD_REQUEST, 
        message=message
      )

  insert_url_query = """
  INSERT INTO url_by_backhalf_alias 
    (backhalf_alias, user_id, original_url, password_hash, is_active) 
  VALUES 
    (?, ?, ?, ?, ?)
  """
  # TODO: Need to figure out how to generate this.
  backhalf_alias = "template"

  # TODO: Need to implement session function
  user_id = "1234-ABC"

  # TODO: Hash the password 
  password_hash = create_url_request.password
  cassandra_session.execute(
    insert_url_query,
    [backhalf_alias, user_id, create_url_request.original_url, password_hash, create_url_request.is_active]
  )
  
  insert_url_by_user_id_query = """
  INSERT INTO url_by_user_id 
    (user_id, backhalf_alias, original_url, is_active, title, created_at) 
  VALUES 
    (?, ?, ?, ?, ?, ?)
  """

  
  insert_url_clicks_query = """
  INSERT INTO url_clicks_by_backhalf_alias 
    (backhalf_alias, total_clicks) 
  VALUES 
    (?, ?)
  """

  

  cassandra_session.execute(
    insert_url_by_user_id_query,
    []
  )

  cassandra_session.execute(
    insert_url_clicks_query,
    []  
  )
  return status.HTTP_201_CREATED

@router.delete("/api/urls/{backhalf_alias}")
async def delete_url(backhalf_alias_url: str):
  '''
  1. Authenticate the user
  2. Verify the user is allowed to actually delete the url:
    - query for the backhalf 
  
  '''
  pass

@router.post("/api/urls/{backhalf_alias}")
async def update_url(backhalf_alias: str):
  pass

# # ------------------------
# Utility or service functions to help url routers
# # ------------------------


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