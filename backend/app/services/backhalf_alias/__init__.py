from .alias_generator import AliasGenerator, get_alias_generator

# Only want to export those two from this package.
# Now we get: from backhalf_alias import AliasGenerator, get_alias_generator
# Instead of: from backhalf_alias.alias_generator import AliasGenerator, get_alias_generator
# You can add other imports though, it doesn't really matter that much.
__all__ = ["AliasGenerator", "get_alias_generator"]
