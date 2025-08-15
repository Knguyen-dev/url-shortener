from datetime import datetime
from cassandra.cluster import Session
from app.services.cassandra import get_cassandra_session

class CassandraUrlByUserRepo:
  def __init__(self, session: Session):
    self.session = session

    self.create_url_prepared = session.prepare(
      """
      INSERT INTO url_by_user_id 
        (user_id, backhalf_alias, original_url, is_active, title, created_at) 
      VALUES 
        (?, ?, ?, ?, ?, ?)
      """      
    )

    self.get_urls_by_user_statement = session.prepare(
      "SELECT * FROM url_by_user_id WHERE user_id = ?",
    )

    self.get_single_url_prepared = session.prepare(
      "SELECT * FROM url_by_user_id WHERE user_id = ? AND backhalf_alias = ?"
    )

    self.delete_single_url_prepared = session.prepare(
      "DELETE FROM url_by_user_id WHERE user_id = ? AND backhalf_alias = ?",
    )

    self.delete_urls_by_user_statement = session.prepare(
      "DELETE FROM url_by_user_id WHERE user_id = ?",
    )

    self.update_url_statement = session.prepare(
      """UPDATE url_by_user_id SET is_active = ?, title = ? WHERE user_id = ? AND backhalf_alias = ?"""
    )

  def create_url(self, user_id: int, backhalf_alias: str, original_url: str, is_active: bool, title: str, created_at: datetime):
    """Creates a URL for a given user
    
    Note: Timestamps are always stored as UTC milliseconds, but Cassandra 
    doesn't store time zone info. Any timezone is auto converted to UTC before  storing
    """
    result = self.session.execute(
      self.create_url_prepared,
      (user_id, backhalf_alias, original_url, is_active, title, created_at,)
    )
    return result
        
  def get_urls_by_user_id(self, user_id: str):
    """Gets all urls for a given user_id"""  
    result = self.session.execute(
      self.get_urls_by_user_statement,
      (user_id,)
    )
    return result
  
  def get_single_url(self, user_id: int, backhalf_alias: str):
    """Returns a single url"""
    result = self.session.execute(
      self.get_single_url_prepared,
      (user_id, backhalf_alias)
    )
    row = result.one()
    if row:
      row = row._asdict()
    return row

    
  def delete_single_url(self, user_id: int, backhalf_alias: str):
    """Deletes a single url with user_id and backhalf_alias"""
    result = self.session.execute(
      self.delete_single_url_prepared,
      (user_id, backhalf_alias,)
    )
    return result
      
  def delete_urls_by_user_id(self, user_id: str):
    """Deletes all urls for a given user_id"""
    result = self.session.execute(
      self.delete_urls_by_user_statement,
      (user_id,)
    )
    return result

  def update_url(self, is_active: bool, title: str, user_id: int, backhalf_alias: str):
    """Updates the attributes of a url"""
    result = self.session.execute(
      self.update_url_statement,
      (is_active, title, user_id, backhalf_alias)
    )
    return result

def get_cassandra_url_by_user_repo():
  """Dependency injection provider for url by user repo"""
  return CassandraUrlByUserRepo(get_cassandra_session())