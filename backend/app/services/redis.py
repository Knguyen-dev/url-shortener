from datetime import datetime, timezone
import redis.asyncio as redis
from app.config import settings
from .logger import app_logger
import asyncio
import time

# The client is a connection pool
# NOTE: Use redis.Redis() to have built in response decoding from bytestrings to strings.
redis_client: redis.Redis = redis.Redis(
  host=settings.REDIS_HOST,
  port=settings.REDIS_PORT,
  db=settings.REDIS_DB,
  decode_responses=True,
  encoding="utf-8"
)

async def init_redis():
  max_retries = 3
  retry_delay = 3
  for attempt in range(1, max_retries + 1):
    try:
      app_logger.info(
        f"Attempting to connect to Redis (attempt {attempt}/{max_retries})"
      )
      await redis_client.ping()
      app_logger.info("Redis Connection Successful")
      return
    except redis.ConnectionError as e:
      app_logger.warning(f"Redis connection attempt {attempt} failed: {e}")
      if attempt == max_retries:
        app_logger.error(
          f"Failed to connect to Redis after {max_retries} attempts: {e}"
        )
        raise RuntimeError(
          f"Redis connection failed after {max_retries} attempts: {e}"
        ) from e
      app_logger.info(f"Retrying Redis connection in {retry_delay} seconds...")
      await asyncio.sleep(retry_delay)
    except Exception as e:
      app_logger.error(f"Unexpected error connecting to Redis (attempt {attempt}): {e}")

      if attempt == max_retries:
        raise RuntimeError(
          f"Redis connection failed after {max_retries} attempts: {e}"
        ) from e

      app_logger.info(f"Retrying in {retry_delay} seconds...")
      await asyncio.sleep(retry_delay)

  # This should never be reached, but just in case
  raise RuntimeError("Redis connection failed: Maximum retries exceeded")

# -----------------------------------------
# Helper functions for urls
# -----------------------------------------
def create_url_click_cache_key(backhalf_alias: str):
  return f"url_click:{backhalf_alias}"

async def cache_delete_url_click(backhalf_alias):
  """Deletes a key-value pair. Returns 1 if the key existed and was deleted, and 0 otherwise"""
  cache_key = create_url_click_cache_key(backhalf_alias)
  return await redis_client.delete(cache_key)


async def cache_increment_url_click(backhalf_alias):
  """Increments the click count in redis for a given key. Returns the new count."""
  cache_key = create_url_click_cache_key(backhalf_alias)

  # Automatically handles both cases:
  # - If field exists: increment by 1
  # - If field doesn't exist :creates it and set to 1
  # Note: Stores
  return await redis_client.incr(cache_key)


async def cache_get_url_click(backhalf_alias):
  """Gets the url click count in Redis for a given url"""
  cache_key = create_url_click_cache_key(backhalf_alias)
  result = await redis_client.get(cache_key)
  return int(result) if result else 0

# -----------------------------------------
# Helper functions for sessions
# -----------------------------------------
def create_session_cache_key(session_token: str) -> str:
  return f"session:{session_token}"

async def cache_update_session(session_token: str, last_active_at: datetime):
  """Updates a session's last_active_at field in the cache
  
  Note: last_active_at is for idle timeouts, not absolute, so 
  you're not going to mess with the TTL on this one. Just update the field.
  Need to convert to ISO 8601 string before storing.
  """
  cache_key = create_session_cache_key(session_token)
  last_active_at_str = last_active_at.isoformat()
  await redis_client.hset(cache_key, "last_active_at", last_active_at_str)

async def cache_set_session(session_obj, expires_at_dt: datetime):
  """Stores a session object in the cache"""
  session_token = session_obj["session_token"]
  cache_key = create_session_cache_key(session_token)

  # Convert Unix timestamp in seconds
  expires_at_ts = int(expires_at_dt.replace(tzinfo=timezone.utc).timestamp())
  now_ts = int(time.time())

  # Calculate remaining seconds left. If it's expired, the expression is negative, 
  # however we do max() function to ensure it's never negative.
  ttl = max(expires_at_ts - now_ts, 0)
  await redis_client.hset(cache_key, mapping=session_obj)
  await redis_client.expire(cache_key, ttl)


async def cache_get_session(session_token: str):
  """Gets a session from the cache by its ID"""
  cache_key = create_session_cache_key(session_token)
  return await redis_client.hgetall(cache_key)

async def cache_delete_session(session_token: str):
  """Deletes a session in the cache by its session id"""
  cache_key = create_session_cache_key(session_token)
  return await redis_client.delete(cache_key)

"""
Typical redis pattern for URLS
- Taking it one step further we can cache urls and redirects themselves. However if you're 
  also doing password-protected links, this can get a little tricky, just know your limits for 
  this kind of stuff.
"""