from cassandra.io.libevreactor import LibevConnection
from cassandra.cluster import Cluster, Session
from cassandra.policies import DCAwareRoundRobinPolicy
import asyncio
from app.config import settings
from .logger import app_logger

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
    app_logger.info(
      f"Keyspace {settings.CASSANDRA_KEYSPACE} ready (created or already exists)"
    )
  except Exception as e:
    app_logger.error(
      f"Error setting up keyspace {settings.CASSANDRA_KEYSPACE} {str(e)}"
    )
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

  for attempt in range(1, max_retries + 1):
    try:
      app_logger.info(
        f"Attempting to connect to Cassandra (attempt {attempt}/{max_retries})"
      )
      _cassandra_cluster = Cluster(
        [settings.CASSANDRA_HOST],
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="dc1"),
        port=settings.CASSANDRA_PORT,
        protocol_version=5,
        connection_class=LibevConnection,
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
        app_logger.error(
          f"Failed to connect to Cassandra after {max_retries} attempts: {e}"
        )
        raise RuntimeError(
          f"Cassandra connection failed after {max_retries} attempts: {e}"
        ) from e

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
