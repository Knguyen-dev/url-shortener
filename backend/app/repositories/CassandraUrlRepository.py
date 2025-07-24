from typing import Dict, Optional
from cassandra.cluster import Cluster, Session
from cassandra.query import SimpleStatement

class CassandraUrlRepository:

  def __init__(self, session: Session):
    self.session = session
    self.get_url_by_alias_statement = session.prepare(
      "SELECT * FROM url_by_backhalf_alias WHERE backhalf_alias = ?"
    )
    self.delete_url_by_alias_statement = session.prepare(
      "DELETE FROM url_by_backhalf_alias WHERE backhalf_alias = ?"
    )
  
  def get_url_by_alias(self, backhalf_alias: str) -> Optional[Dict[any, any]]:
    """Gets a URL using the backhalf alias"""
    try:
      result = self.session.execute(
        self.get_url_by_alias_statement,
        (backhalf_alias,)
      )
      return result
    except Exception as e:
      raise  


  

  
  
     
  