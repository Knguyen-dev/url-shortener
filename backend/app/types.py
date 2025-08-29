from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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
  email: EmailStr = Field(title="Email of the user", min_length=5, max_length=64)
  full_name: str = Field(title="Full name of the user", min_length=1, max_length=32)
  password: str
  confirm_password: str

  @field_validator("email", mode="before")
  def normalize_email(cls, v):
    return v.lower().strip()

  @field_validator("full_name", mode="before")
  def normalize_full_name(cls, v):
    return v.strip()

  @field_validator("password", mode="after")
  @classmethod
  def validate_password_strength(cls, password: str) -> str:
    """
    + Password regex, same as the one on the front-end:
    1. ^: start of the string
    2. (?=.*[a-z]): Checks for at least one lower case letter
    3. (?=.*[A-Z]): Checks for at least one upper case letter
    4. (?=.*\d): Checks for at least one digit
    5. (?=.*[!@#$%^&*]): Checks for at least one of those 'special' characters listed between the brackets
    6. (?!.*\s): No white spaces for entire string, which makes sense since it's a password.
    7. .{8, 40}: String is at least 8 characters and at most 40.
    8. $: End of the string
    """
    password_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*])(?!.*\s).{8,40}$"
    if not password_regex.match(password):
      raise ValueError(
        "Password must be 8-40 characters long, contain at least one uppercase letter, one lowercase letter, one number, and one special character (!@#$%^&*), and have no spaces."
      )
    return password

  # NOTE: Use model validator to compare multiple fields whilst regular
  # field_validator can't cross-reference. Basically "after" means that this runs after pydantic checks the types
  # and other constraints we defined like Field(min_length=1), etc.
  # https://docs.pydantic.dev/latest/concepts/validators/#using-the-decorator-pattern
  @model_validator(mode="after")
  def check_passwords_match(self):
    if self.password != self.confirm_password:
      raise ValueError("Password fields do not match!")
    return self


class LoginRequest(BaseModel):
  # NOTE: Good practice to have constraints to the login's input fields:
  # - Prevents maliciously long inputs that could cause DoS attacks.
  # - Also for data integrity as we ensure the data being processed by the login route
  # is within reasonable limits.

  # The email should have constraints to prevent excessively long inputs.
  # The max length of 254 is the standard (RFC 5322) for email addresses.
  email: EmailStr = Field(max_length=254)

  # The password field should have constraints that mirror the signup process.
  # This prevents unnecessarily long inputs and ensures a consistent API contract.
  # The min_length of 8 and max_length of 32 are examples. Though you'll still let
  # stuff like regex validation be handled on the signup process.
  password: str = Field(min_length=8, max_length=32)


# #----------------------------------
# Url router models
# # ---------------------------------
class CreateUrlRequest(BaseModel):
  original_url: str
  password: Optional[str] = None
  confirm_password: Optional[str] = None
  is_active: bool
  title: str = Field(min_length=1, max_length=64)

  @field_validator("title", mode="before")
  @classmethod
  def normalize_title(cls, title: str) -> str:
    return title.strip()

  @field_validator("password", mode="after")
  @classmethod
  def validate_password_strength(cls, password: Optional[str]) -> Optional[str]:
    if password is None:
      return password

    # If password is defined, make sure it's between 5-20 characters long and alphanumeric only.
    # Note: We don't require special characters, uppercase, lowercase, etc. for url passwords
    if not password.isalnum():
      raise ValueError("Password must contain alphanumeric characters only.")

    min_length = 5
    max_length = 20
    if not (min_length <= len(password) <= max_length):
      raise ValueError(
        f"Password must be between {min_length} and {max_length} characters long."
      )
    return password

  @model_validator(mode="after")
  def check_passwords_match(self):
    if self.password != self.confirm_password:
      raise ValueError("Passwords do not match for the password-protected url!")
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
  """Request body model for when a user is trying to access a passwor-protected url.

  NOTE: Make sure the length constraints match those defined in CreateUrlRequest to
  ensure some consistency and reasonable limits.
  """

  password: str = Field(min_length=5, max_length=20)


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

  @field_validator("title", mode="before")
  @classmethod
  def normalize_title(cls, title: str) -> str:
    return title.strip()

  @field_validator("title", mode="ater")
  @classmethod
  def validate_title(cls, title: str) -> str:
    if title is None:
      return title

    # title: str = Field(min_length=1, max_length=64)
    if not (1 <= len(title) <= 64):
      raise ValueError("Title must be between 1 and 64 characters long.")
    return title

  @field_validator("password", mode="after")
  @classmethod
  def validate_password_strength(cls, password: Optional[str]) -> Optional[str]:
    if password is None:
      return password

    # NOTE: Make sure these constraints match those defined in CreateUrlRequest
    if not password.isalnum():
      raise ValueError("Password must contain alphanumeric characters only.")

    min_length = 5
    max_length = 20
    if not (min_length <= len(password) <= max_length):
      raise ValueError(
        f"Password must be between {min_length} and {max_length} characters long."
      )
    return password

  @model_validator(mode="after")
  def check_passwords_match(self):
    """
    NOTE: For this to work, either both word and confirm_password are defined (for change)
    or neither are defined (for no change). If only one is defined, then raise an error.
    The conditional below checks for this.
    """
    if self.password != self.confirm_password:
      raise ValueError("Passwords do not match for the password-protected url!")
    return self


class UrlInfoResponse(BaseModel):
  """Data model representing the comprehensive information about a URL, including its details and click statistics."""

  url_by_backhalf_alias: UrlByBackhalfAlias
  url_by_user_id: UrlByUserId
  total_clicks: int
