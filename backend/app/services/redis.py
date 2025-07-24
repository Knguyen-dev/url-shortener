import redis.asyncio as redis
from app.config import settings
from .logger import app_logger

redis_client: redis.Redis = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True,  # optional: returns str instead of bytes, probably recommended
  )

async def init_redis():
  try:
    await redis_client.ping()
    app_logger.info("Redis Connection Successful")
  except redis.ConnectionError as e:
    app_logger.info(f"Redis Connection Failed: {str(e)}")
    raise

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

def cache_delete_url_click(backhalf_alias):
  """Deletes a key-value pair"""
  cache_key = f"url_click:{backhalf_alias}"
  return redis_client.delete(cache_key)

def cache_increment_url_click(backhalf_alias):
  """Increments the click count in redis for a given key"""
  cache_key = f"url_click:{backhalf_alias}"

  # Automatically handles both cases:
  # - If field exists: increment by 1
  # - If field doesn't exist :creates it and set to 1
  # Note: Stores 
  return redis_client.incr(cache_key)  

def cache_get_url_click(backhalf_alias):
  """Gets the url click count in Redis for a given url"""
  cache_key = f"url_click:{backhalf_alias}"
  result = redis_client.get(cache_key)
  return result if result else 0
  
# -----------------------------------------
# Helper functions for sessions
# -----------------------------------------
# TODO




