from cassandra.io.libevreactor import LibevConnection
from cassandra.cluster import Cluster, Session
from cassandra.policies import DCAwareRoundRobinPolicy
import asyncio
from app.config import settings
from .logger import app_logger

"""
## Database Design Notes

### URLs table
This is the main table for URL mappings. Used for redirection query.    
- backhalf_alias: The short code that identifies a shortened url. 
- original_url: Original url that it links to.
- user_id: Id of the user who created the url. Needed for access control for stuff like 
  updating a url. User provides the backhalf_alias and their user_id, we need to make sure 
  the url being modified matches these creds? No I think it's moreso allows us to 
  look into the urls by user table?
- password_hash: Password hash protecting the url, needed in case for a password prompt 
- is_active: Whether the link is active or not, needed for whether we do the redirect

NOTE: Don't need a title here because no one's going to see a title during a redirect

### URLs by User ID
Table for showing all URLs for a given user (dashboard query).
This table is also used for any MODIFYING requests made to a url:
  
Attributes:
- user_id: A int from the postgres database. This doesn't need to be uuid though.
- backhalf_alias: The code uniquely identifying the url. This is necessary to reference 
  the actual url in the urls table.
- original_url: Needed since you probably want to show the user the original url on the dashboard. 
- is_active: You definitely want to show whether and know whether or not a url is active for the user.
- title: You want to show the title of the url as well since the user by want to name their url. You 
wouldn't need to show the title when re-directing the user, which is what the firrst table is for.

We have a composite primary key, ensuring that each `user_id` can have multiple 
backhalf_alias entires, and that each (user_id, backhalf_alias) pair is unique. 
This allows us to query all urls for a given user, or even narrow down the search to a single url.
This should already be unique because each backhalf_alias is unique.


Operations and how to use:
- Deleting a url:
  - By user id: Query by user_id, then get the backhalf_alias and delete from all tables using it. Multiple queries though.
  - By short code: Query by user_id first, get back_half alias from all tables.   
  Other operations are following the same idea.
      
Note: Ordered it by creation date so that the most recent are returned first. Also password_hash
isn't in here because I don't think it's that serious to prompt the user for a current password 
with links.

### URL clicks table
URL clicks table - table for tracking the number of clicks a 
url has gotten. This is definitely needed for the dashboard to see analytics.
You can have it as an additional analytics button or 

- backhalf_alias: The shortened code for a url.
- total_clicks: The total amount of clicks for a url

Note: In Cassandra, due to how it's implemeented under the hood,
you can only have COUNTER column in a table with a primary key and other 
counter columns.

## Note About Cassandra
About Cassandra: The Cluster object manages a pool of connections automatically, meaning 
you don't have to manually deal with opening and closing a connection for each request, so
keeping a global session is the recommendation approach with the Cassandra driver.
"""

from cassandra.io.libevreactor import LibevConnection
from cassandra.cluster import Cluster

_cassandra_cluster: Cluster = None
_cassandra_session: Session = None

def get_cassandra_session() -> Session:
    """Returns a reference to the Cassandra session"""
    if _cassandra_session is None:
        raise RuntimeError("Cassandra session wasn't initialized")
    return _cassandra_session

def create_keyspace(cassandra_session: Session):
  """Creates the urlshortener keyspace if it doesn't already exist"""
  if not cassandra_session:
    raise Exception("Cassandra cluster isn't initialized.")
  
  try:
      cassandra_session.execute(f"""
          CREATE KEYSPACE IF NOT EXISTS {settings.CASSANDRA_KEYSPACE}
          WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': '1'}}
      """)
      app_logger.info(f"Keyspace {settings.CASSANDRA_KEYSPACE} ready (created or already exists)")
  except Exception as e:
    app_logger.error(f"Error setting up keyspace {settings.CASSANDRA_KEYSPACE} {str(e)}")
    raise

def create_tables(cassandra_session: Session):
  """Create necessary tables for the URL shortener if they don't already exist"""
  if not cassandra_session:
    raise Exception("Cassandra session not initialized")

  create_urls_table = """
    CREATE TABLE IF NOT EXISTS url_by_backhalf_alias (
      backhalf_alias TEXT PRIMARY KEY,
      user_id int,
      original_url TEXT,
      password_hash TEXT,
      is_active BOOLEAN
    )
    """

  create_url_by_user = """
    CREATE TABLE IF NOT EXISTS url_by_user_id (
      user_id int,
      backhalf_alias TEXT,
      original_url TEXT,
      is_active BOOLEAN,
      title TEXT,
      created_at TIMESTAMP,
      PRIMARY KEY (user_id, backhalf_alias)
    )
    """

  create_clicks_table = """
    CREATE TABLE IF NOT EXISTS url_clicks_by_backhalf_alias (
      backhalf_alias TEXT PRIMARY KEY,
      total_clicks COUNTER 
    )
    """

  # Execute table creation
  tables = [
    ("urls", create_urls_table),
    ("user_urls", create_url_by_user),
    ("url_clicks", create_clicks_table),
  ]

  for table_name, create_statement in tables:
    try:
      cassandra_session.execute(create_statement)
      app_logger.info(f"Table '{table_name}' ready (created or already exists)")
    except Exception as e:
      app_logger.error(f"Error setting up table '{table_name}': {e}")
      raise

async def init_cassandra():
  """Initialize Cassandra connection and create tables"""
  global _cassandra_cluster, _cassandra_session
  
  max_retries = 5
  retry_delay = 10
  
  for attempt in range(1, max_retries+1):
    try:
      app_logger.info(f"Attempting to connect to Cassandra (attempt {attempt}/{max_retries})")
      _cassandra_cluster = Cluster(
        [settings.CASSANDRA_HOST],
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="dc1"), 
        port=settings.CASSANDRA_PORT, 
        protocol_version=5, 
        connection_class=LibevConnection 
      )
      _cassandra_session = _cassandra_cluster.connect()
      create_keyspace(_cassandra_session)
      _cassandra_session.set_keyspace(settings.CASSANDRA_KEYSPACE)

      app_logger.info("Cassandra Connection Successful")

      create_tables(_cassandra_session)
      app_logger.info("Cassandra initialization complete")
      return
    
    except Exception as e:
      app_logger.warning(f"Cassandra connection attempt {attempt} failed: {str(e)}")
      
      if attempt == max_retries:
        app_logger.error(f"Failed to connect to Cassandra after {max_retries} attempts: {e}")
        raise RuntimeError(f"Cassandra connection failed after {max_retries} attempts: {e}") from e
      
      _cassandra_cluster.shutdown()
      app_logger.info(f"Retrying Cassandra connection in {retry_delay} seconds...")
      await asyncio.sleep(retry_delay)

  # This shuoldn't be reached, but just in case we completely fail to connect 
  raise RuntimeError("Cassandra connection failed: Maximum retries exceeded")


def shutdown_cassandra():
  """Shutdown cassandra in a graceful way"""
  global _cassandra_cluster
  app_logger.info("Shutting down Cassandra connection.")
  _cassandra_cluster.shutdown()
  _cassandra_cluster = None
