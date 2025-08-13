from cassandra.cluster import Session
from app.services.logger import app_logger
from app.services.cassandra import get_cassandra_session

class CassandraClickRepo:
  def __init__(self, session: Session):
    self.session = session

    # Note: Due to the nature of cassandra, you can't insert into a counter. You can use this statement to 
    # either create a new row or update an existing row.
    self.update_clicks_statement = session.prepare(
      "UPDATE url_clicks_by_backhalf_alias SET total_clicks = total_clicks + ? WHERE backhalf_alias = ?"
    )

    self.get_clicks_statement = session.prepare(
      "SELECT total_clicks FROM url_clicks_by_backhalf_alias WHERE backhalf_alias = ?"
    )

    self.delete_clicks_statement = session.prepare(
      "DELETE FROM url_clicks_by_backhalf_alias WHERE backhalf_alias = ?"
    )

  def update_url_clicks(self, backhalf_alias: str, click_count: int):
    """Increments the total_clicks for a given backhalf_alias.
    This function handles both updating an existing row, or creating the row 
    if it doesn't already exist.

    Args:
        backhalf_alias (str): Alias for the url
        click_count (int): The number of clicks to add
    """
    self.session.execute(
      self.update_clicks_statement,
      (click_count, backhalf_alias)
    )
    

  def get_total_clicks(self, backhalf_alias: str) -> int:
    """Retrieves the total_clicks for a givne backhalf_alias

    Args:
        backhalf_alias (str): Alias for the url

    Returns:
        int: The total number of clicks, or 0 not found.
    """
    row = self.session.execute(
      self.get_clicks_statement,
      (backhalf_alias,)
    )
    return row["total_clicks"] if row else 0
    

  def delete_clicks(self, backhalf_alias: str) -> None:
    """Deletes a row by backhalf_alias 

    Args:
        backhalf_alias (str): Alias of the url.
    """
    self.session.execute(
      self.delete_clicks_statement,
      (backhalf_alias,)
    )
    
def get_cassandra_click_repo():
  return CassandraClickRepo(get_cassandra_session())