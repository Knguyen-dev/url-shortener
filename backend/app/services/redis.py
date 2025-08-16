import redis.asyncio as redis
from app.config import settings
from .logger import app_logger
import asyncio

redis_client: redis.Redis = redis.from_url(settings.REDIS_URL)

async def init_redis():
  max_retries = 3 
  retry_delay = 3
  for attempt in range(1, max_retries+1):
    try:
      app_logger.info(f"Attempting to connect to Redis (attempt {attempt}/{max_retries})")
      await redis_client.ping()
      app_logger.info("Redis Connection Successful")
      return
    except redis.ConnectionError as e:
      app_logger.warning(f"Redis connection attempt {attempt} failed: {e}")
      if attempt == max_retries:
          app_logger.error(f"Failed to connect to Redis after {max_retries} attempts: {e}")
          raise RuntimeError(f"Redis connection failed after {max_retries} attempts: {e}") from e
      app_logger.info(f"Retrying Redis connection in {retry_delay} seconds...")
      await asyncio.sleep(retry_delay)
    except Exception as e:
      app_logger.error(f"Unexpected error connecting to Redis (attempt {attempt}): {e}")
      
      if attempt == max_retries:    
        raise RuntimeError(f"Redis connection failed after {max_retries} attempts: {e}") from e
    
      app_logger.info(f"Retrying in {retry_delay} seconds...")
      await asyncio.sleep(retry_delay)

  # This should never be reached, but just in case
  raise RuntimeError("Redis connection failed: Maximum retries exceeded")

# -----------------------------------------
# Helper functions for urls
# -----------------------------------------
'''
Typical redis pattern for URLS
- Instead of updating the database all at once with click counts we can 
  keep a running count of clicks in Redis. Then every like 10 clicks we flush it all
  to the database. As a result, you're reducing load on the database in a smart way with 
  caching.
- Taking it one step further we can cache urls and redirects themselves. However if you're 
  also doing password-protected links, this can get a little tricky, just know your limits for 
  this kind of stuff.
'''

async def cache_delete_url_click(backhalf_alias):
  """Deletes a key-value pair. Returns 1 if the key existed and was deleted, and 0 otherwise"""
  cache_key = f"url_click:{backhalf_alias}"
  return await redis_client.delete(cache_key)

async def cache_increment_url_click(backhalf_alias):
  """Increments the click count in redis for a given key. Returns the new count.
  """
  cache_key = f"url_click:{backhalf_alias}"

  # Automatically handles both cases:
  # - If field exists: increment by 1
  # - If field doesn't exist :creates it and set to 1
  # Note: Stores 
  return await redis_client.incr(cache_key)  

async def cache_get_url_click(backhalf_alias):
  """Gets the url click count in Redis for a given url"""
  cache_key = f"url_click:{backhalf_alias}"
  result = await redis_client.get(cache_key)
  return int(result) if result else 0
  
# -----------------------------------------
# Helper functions for sessions
# -----------------------------------------
# TODO




