# Environment variables for Postgres, Cassandra, and Redis
import os
from pydantic_settings import BaseSettings
from datetime import timedelta
from app.services.logger import app_logger
from dotenv import load_dotenv

load_dotenv()

def get_env_with_logging(key: str, default: str = None) -> str:
    """Get environment variable with logging"""
    value = os.getenv(key, default)
    if not value:
        app_logger.warning(f"Environment variable '{key}' not found, using default: {default}")
        value = default
    return value

class Settings(BaseSettings):
  # Postgres Credentials
  POSTGRES_HOST: str = get_env_with_logging("POSTGRES_HOST", "")
  POSTGRES_PORT: int = get_env_with_logging("POSTGRES_PORT", "")
  POSTGRES_DB: str = get_env_with_logging("POSTGRES_DB", "")
  POSTGRES_USER: str = get_env_with_logging("POSTGRES_USER", "")
  POSTGRES_PASSWORD: str = get_env_with_logging("POSTGRES_PASSWORD", "")
  POSTGRES_URL: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

  # Cassandra Credentials
  CASSANDRA_HOST: str = get_env_with_logging("CASSANDRA_HOST", "cassandra")
  CASSANDRA_PORT: str = get_env_with_logging("CASSANDRA_PORT", "9042")
  CASSANDRA_KEYSPACE: str = get_env_with_logging("CASSANDRA_KEYSPACE", "urlshortener")
  
  # Redis Credentials; 
  REDIS_URL: str = get_env_with_logging("REDIS_URL", "")
  
  ENVIRONMENT: str = get_env_with_logging("ENVIRONMENT", "DEVELOPMENT")
  IS_PRODUCTION: bool = ENVIRONMENT == "PRODUCTION"

  # Session Authentication 
  SESSION_IDLE_LIFETIME: timedelta = timedelta(minutes=30)
  SESSION_ABSOLUTE_LIFETIME: timedelta = timedelta(hours=3)
  SESSION_COOKIE_NAME: str = "session_id"
  
  COOKIE_SECURE: bool = IS_PRODUCTION

settings = Settings()
