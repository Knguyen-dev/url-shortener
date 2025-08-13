from typing import Optional, Self
from fastapi import HTTPException
from pydantic import BaseModel, EmailStr, Field, model_validator


# #----------------------------------
# Auth router models
# # ---------------------------------
class SignupRequest(BaseModel):
  # TODO: Real app would have length constraints and probably your own email validation regex 
  # to have explainability for frontend and backend.
  email: EmailStr
  full_name: str = Field(title="Full name of the user", min_length=1, max_length=32)

  # TODO: In a real app, you'd put some password constraints
  password: str = Field(title="Password of the user", min_length=8, max_length=32)
  confirm_password: str

  # TODO: This works but the error handling isn't uniformalized. Shuold use 
  # native way of doing this. I suggest just creating a validate() function
  # and setting it up so that you call .validate() during the route handler 
  # and this validate function should handle raising all errors. For now it doesn't 
  # really matter, but in a real app you'd want full control

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
  password: Optional[str]
  confirm_password: Optional[str]
  is_active: bool
  title: str = Field(min_length=1)

  @model_validator(mode="after")
  def check_passwords_match(self) -> Self:
    if self.password != self.confirm_password:
      raise ValueError("Passwords do not match!")
    return self
  
class UrlPasswordRequest(BaseModel):
  password: str

class UpdateUrlRequest(BaseModel):
  title: str
  password: Optional[str]
  confirm_password: Optional[str]
  is_active: bool
  