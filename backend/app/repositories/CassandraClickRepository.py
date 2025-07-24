from cassandra.cluster import Session


# Note: The repository pattern follows a specific naming. A prefix containing the technology, the click business that the repository manages,
# and then the name repository.

class CassandraClickRepository:
  def __init__(self, session: Session):
    self.session = session

    # Prepares the statement for efficiency. It allows Casandra to parse and optimize the query once.
    # This is just best practice.
    self.update_clicks_statement = session.prepare(
      "UPDATE url_clicks_by_backhalf_alias SET total_clicks = total_clicks + ? WHERE backhalf_alias = ?"
    )

    self.get_clicks_statement = session.prepare(
      "SELECT total_clicks FROM url_clicks_by_backhalf_alias WHERE backhalf_alias = ?"
    )

    self.delete_clicks_statement = session.prepare(
      "DELETE FROM url_clicks_by_backhalf_alias WHERE backhalf_alias = ?"
    )

  def increment_clicks(self, backhalf_alias: str, click_count: int):
    """Increments the total_clicks for a given backhalf_alias

    Args:
        backhalf_alias (str): Alias for the url
        click_count (int): The number of clicks to add
    """
    try:
      self.session.execute(
        self.update_clicks_statement,
        (click_count, backhalf_alias)
      )
    except Exception as e:
      raise

  def get_total_clicks(self, backhalf_alias: str) -> int:
    """Retrieves the total_clicks for a givne backhalf_alias

    Args:
        backhalf_alias (str): Alias for the url

    Returns:
        int: The total number of clicks, or 0 not found.
    """
    try:
      row = self.session.execute(
        self.get_clicks_statement,
        (backhalf_alias,)
      )
      return row["total_clicks"] if row else 0
    except Exception as e:
      raise

  def delete_clicks(self, backhalf_alias: str) -> None:
    """Deletes a row by backhalf_alias 

    Args:
        backhalf_alias (str): Alias of the url.
    """
    try:
      self.session.execute(
        self.delete_clicks_statement,
        (backhalf_alias,)
      )
    except Exception as e:
      raise
