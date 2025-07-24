# Environment variables for Postgres, Cassandra, and Redis
import os
from pydantic_settings import BaseSettings
from datetime import timedelta
from services.logger import app_logger


def get_env_with_logging(key: str, default: str = None, required: bool = False) -> str:
    """Get environment variable with logging"""
    value = os.getenv(key, default)
    
    if value is None and required:
        app_logger.error(f"Required environment variable '{key}' is not set")
        raise ValueError(f"Required environment variable '{key}' is not set")
    elif value == default and default is not None:
        app_logger.warning(f"Environment variable '{key}' not found, using default: {default}")
    
    return value

class Settings(BaseSettings):
  # Postgres Credentials
  POSTGRES_HOST: str = get_env_with_logging("POSTGRES_HOST", "localhost")
  POSTGRES_PORT: int = get_env_with_logging("POSTGRES_PORT", "5432")
  POSTGRES_DB: str = get_env_with_logging("POSTGRES_DB", "postgres")
  POSTGRES_USER: str = get_env_with_logging("POSTGRES_USER", "dev")
  POSTGRES_PASSWORD: str = get_env_with_logging("POSTGRES_PASSWORD", "devpass")
  POSTGRES_URL: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

  # Cassandra Credentials
  CASSANDRA_HOST: str = get_env_with_logging("CASSANDRA_HOST", "localhost")
  CASSANDRA_PORT: str = get_env_with_logging("CASSANDRA_PORT", "9042")
  CASSANDRA_KEYSPACE: str = get_env_with_logging("CASSANDRA_KEYSPACE", "urlshortener")
  CASSANDRA_USER: str = get_env_with_logging("CASSANDRA_USER", "cassandra")
  CASSANDRA_PASS: str = get_env_with_logging("CASSANDRA_PASS", "cassandra")

  # Redis Credentials
  REDIS_HOST: str = get_env_with_logging("REDIS_HOST", "localhost")
  REDIS_PORT: str = get_env_with_logging("REDIS_PORT", "6379")
  REDIS_DB: str = get_env_with_logging("REDIS_DB", "0")
  REDIS_PASSWORD: str = get_env_with_logging("REDIS_PASSWORD", "")

  environment: str = get_env_with_logging("ENVIRONMENT", "development")

  # Session Authentication 
  SESSION_LIFETIME: timedelta = timedelta(minutes=30) 
  SESSION_COOKIE_NAME: str = "session_id"
  
  COOKIE_SECURE: str = environment == "production" 

settings = Settings()
