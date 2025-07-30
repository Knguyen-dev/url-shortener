from contextlib import asynccontextmanager
from fastapi import FastAPI 
from .services.postgres import init_postgres, cleanup_postgres
from .services.cassandra import init_cassandra, shutdown_cassandra
from .services.redis import init_redis
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

docs_description = """
## Welcome to the Url-Shortener Developer Docs!
Here you can find information on the available endpoints and how to use them. 
"""

@asynccontextmanager
async def startup_event(app: FastAPI):

  # Start up
  await init_redis()
  await init_postgres()
  await init_cassandra()
  
  yield 

  # # Shutdown
  await cleanup_postgres() 
  shutdown_cassandra()

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