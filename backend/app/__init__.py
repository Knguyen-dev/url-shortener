from contextlib import asynccontextmanager
from fastapi import FastAPI 
from .services.postgres import init_postgres
from .services.cassandra import init_cassandra
from .services.redis import init_redis
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

docs_description = """
## Welcome to the Url-Shortener Developer Docs!
Here you can find information on the available endpoints and how to use them. 
"""

@asynccontextmanager
async def startup_event(app: FastAPI):
  # Connect to PostgreSQL, Cassandra, and Redis
  await init_postgres()
  init_cassandra()
  await init_redis()
  yield

app = FastAPI(
  lifespan=startup_event,
  description=docs_description,
  title="PII-Redacter Developer Docs",
  version="1.0.0",
)  # Create FastAPI app with this startup event

# Allow front-end to make requests
app.add_middleware(
  # TODO: I could probably harden down on this
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,  # Allow cookies to be transferred either way
  allow_methods=["*"],
  allow_headers=["*"],
)