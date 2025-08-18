from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator


# #----------------------------------
# Auth router models
# # ---------------------------------
class UserInfoResponse(BaseModel):
  """Data model representing the user information returned by the API.

  The main reason this exists is to be able to return non-sensitive user information
  back to client after login, after verifying credentials, etc. You'd avoid sending
  sensitive information like password hashes, etc.
  """

  id: int
  email: EmailStr
  full_name: str
  is_admin: bool
  created_at: datetime  # Automatically converted to ISO format datetime string when sent to client (thanks to FastAPI)


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
  def check_passwords_match(self):
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
  password: Optional[str] = None
  confirm_password: Optional[str] = None
  is_active: bool
  title: str = Field(min_length=1)

  @model_validator(mode="after")
  def check_passwords_match(self):
    if self.password != self.confirm_password:
      raise ValueError("Passwords do not match!")
    return self


class UrlByBackhalfAlias(BaseModel):
  """Data model representing a URL fetched by its backhalf alias.
  This should match its corresponding DB model."""

  backhalf_alias: str
  user_id: int
  original_url: str
  password_hash: Optional[str] = None
  is_active: bool


class UrlByUserId(BaseModel):
  """Data model representing a URL fetched by its user ID. This
  data model is used mainly when we want to show urls on a user's dashboard.
  This should match its corresponding DB model.

  Note: This is also used for the response when the user creates a url.
  The idea is that when a user creates a url, we'd also want to show that
  URL on the user's dashboard.
  """

  user_id: int
  backhalf_alias: str
  original_url: str
  is_active: bool
  title: str
  created_at: (
    datetime  # When returned to the client, FastAPI converts this to ISO format string.
  )

class UrlPasswordRequest(BaseModel):
  password: str


class UpdateUrlRequest(BaseModel):
  """
  Operations:
  - Change the title
  - Change the password
  - Remove Password
  - Activate and deactivate the url
  """

  title: Optional[str] = None  # new title, or none meaning no change
  password: Optional[str] = None  # new password, or None means no change
  confirm_password: Optional[str] = None
  is_remove_password: bool = False  # explicitly remove password protection on link
  is_active: Optional[bool] = None  # new active state, or none meaning no change


class UrlInfoResponse(BaseModel):
  """Data model representing the comprehensive information about a URL, including its details and click statistics."""

  url_by_backhalf_alias: UrlByBackhalfAlias
  url_by_user_id: UrlByUserId
  total_clicks: int
