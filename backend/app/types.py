from typing import Self
from pydantic import BaseModel, EmailStr, Field, model_validator


# #----------------------------------
# Auth router models
# # ---------------------------------
class SignupRequest(BaseModel):
  email: EmailStr
  full_name: str = Field(title="Full name of the user", min_length=1, max_length=32)
  password: str = Field(title="Password of the user", min_length=8, max_length=32)
  confirm_password: str

  # TODO: Does this actually work?
  # NOTE: Use model validator to compare multiple fields whilst regular 
  # field_validator can't cross-reference.
  # https://docs.pydantic.dev/latest/concepts/validators/#using-the-decorator-pattern
  @model_validator(mode="after")
  def check_passwords_match(self) -> Self:
    if self.password != self.confirm_password:
      raise ValueError("Passwords do not match!")
    return self

class LoginRequest(BaseModel):
  email: EmailStr
  password: str = Field(min_length=1)

# #----------------------------------
# Url router models
# # ---------------------------------
class CreateUrlRequest(BaseModel):
  # TODO: Should probably have server side input validation here
  original_url: str = Field(min_length=1)
  password: str
  confirm_password: str
  is_active: bool
  title: str
  

