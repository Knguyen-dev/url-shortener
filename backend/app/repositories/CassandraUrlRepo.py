from typing import Dict, Optional
from cassandra.cluster import Session, ResultSet
from app.services.cassandra import get_cassandra_session


class CassandraUrlRepo:
  def __init__(self, session: Session):
    self.session = session


    
    self.get_url_prepared = session.prepare(
      "SELECT * FROM url_by_backhalf_alias WHERE backhalf_alias = ?"
    )

    self.create_url_prepared = session.prepare("""
      INSERT INTO url_by_backhalf_alias (
          backhalf_alias, user_id, original_url, password_hash, is_active
      ) VALUES (?, ?, ?, ?, ?)
    """)



    self.delete_url_by_alias_statement = session.prepare(
      "DELETE FROM url_by_backhalf_alias WHERE backhalf_alias = ?"
    )

    self.update_url_by_alias_statement = session.prepare(
      """
      UPDATE url_by_backhalf_alias 
      SET 
        is_active = ?, password_hash = ? 
      WHERE 
        backhalf_alias = ?
      """
    )


  def create_url(self, backhalf_alias: str, user_id: int, original_url: str, password_hash: Optional[str], is_active: bool):
    """Creates a url"""
    result = self.session.execute(
      self.create_url_prepared,
      (backhalf_alias, user_id, original_url, password_hash, is_active,) 
    )
    return result

  def get_url_by_alias(self, backhalf_alias: str) -> Optional[Dict[any, any]]:
    """Gets a URL using the backhalf alias"""
    result: ResultSet = self.session.execute(
      self.get_url_prepared,
      (backhalf_alias,)
    )
    
    # After result.one()
    # Type: <class 'cassandra.io.libevreactor.Row'>
    # Row(backhalf_alias='2KTW8q30J8K', is_active=False, original_url='https://example.com/articles/georgian', password_hash='$2b$12$caLwiY54jxMoACIN0z9UFOcKzDumcIuj7Fup84NBv1LtRIyQP3fpm', user_id=3)
    # Note: Can't do result.one()._asdict() because if we didn't find anything, and run ._asdict() on it, 
    # then we'll get an error. 
    row = result.one()
    if row:
      row = row._asdict()
    return row    
    
  def delete_url_by_alias(self, backhalf_alias: str):
    """Deletes a URL using the backhalf alias"""
    result = self.session.execute(
      self.delete_url_by_alias_statement,
      (backhalf_alias,)
    )
    return result

  def update_url_by_alias(self, is_active: bool, password_hash: str, backhalf_alias: str):
    """Updates a URL using the backhalf alias"""
    result = self.session.execute(
      self.update_url_by_alias_statement,
      (is_active, password_hash, backhalf_alias)
    )
    return result

def get_cassandra_url_repo():
  """Dependency injection provider for the url repo"""
  return CassandraUrlRepo(get_cassandra_session())