base = 62
character_set = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
character_to_value = {} 
for index in range(len(character_set)):
  char = character_set[index]
  character_to_value[char] = index

# NOTE: The dictionary allows O(1) look-ups on from_base_62

def encode_base_62(num: int) -> str:
  """Converts a number into a base62 string"""  
  if num == 0:
    return "0"
  
  encoded_str = ""
  while num > 0:
    remainder = num % base 
    num = num // base
    encoded_str = character_set[remainder] + encoded_str
  return encoded_str

def decode_base_62(str: str) -> int:
  """Convert a base62 encoded string into a base 10 number"""
  total = 0
  for index, char in enumerate(reversed(str)):
    value = character_to_value[char]
    total += value * (base ** index)
  return total