from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse 
from .services.postgres import init_postgres, cleanup_postgres
from .services.cassandra import init_cassandra, shutdown_cassandra
from .services.redis import init_redis
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

# Import the routes 
from .routes.auth_router import auth_router
from .routes.user_router import user_router
from .routes.url_router import url_router


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

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
  """Middleware that uniformalizes how errors are sent back to the frontend."""
  err_content = {"status_code": exc.status_code, "message": exc.detail}
  return JSONResponse(
    status_code=exc.status_code,
    content=err_content,
  )


app.include_router(auth_router, tags=["auth"])
app.include_router(user_router, tags=["users"])
app.include_router(url_router, tags=["urls"])


# Not found 