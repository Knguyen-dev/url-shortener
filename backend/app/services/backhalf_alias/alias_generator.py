from .base62 import encode_base_62
from .snowflake_generator import SnowflakeGenerator


class AliasGenerator:
  def __init__(self):
    """
    Class that generates your backhalf aliases for your urls

    Important:
    Whilst your API is running you probably want to keep this class, in particular
    your sequence generator in memory. The reason for this is because regardless of
    whether you're using snowflake or SimpleSeqGenerator, you gain the most efficiency
    keeping that sequence number in memory. For example, in Snowflake IDs we have
    that sequence number for being able to generate multiple snowflake ids per
    millisecond. If we just instantiate the instance for every request and then
    throw it to garbage collection, we are literally only using it for one uid.

    To keep it in memory, we have to create one class instance of this and
    keep using that class instance for the remainder that our API is active. But how?
    There are actually a couple of ways to do this:

    Dependency Injection: We create a single instance (singleton) and our framework handles injecting
    it in our routes when we need it. You'd have to lean on a framework that provides this,
    but almost all frameworks provides this. We already use this in the app. Just define
    a get_alias_generator function and use Depends().
    """

    # TODO: If you're scaling this up, make sure each UID generation
    # service has a different UID
    self.worker_id = 0  # your worker_id/machine_id

    # Note: If you want shorter urls, use simple sequence generation
    self.sequence_generator = SnowflakeGenerator(worker_id=self.worker_id)

  def generate_backhalf_alias(self):
    uid = self.sequence_generator.next_id()
    backhalf_alias = encode_base_62(uid)
    return backhalf_alias


_alias_generator = AliasGenerator()


def get_alias_generator() -> AliasGenerator:
  """Returns an instance of alias generator

  Note: Use this with dependency injection!
  """
  return _alias_generator
