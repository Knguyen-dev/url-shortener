# Url Shortener

A robust and efficient URL shortener built for fast redirects and reliable link management.

## Table of Contents
1. Features
2. Getting Started
3. Usage
4. API Reference
5. Technical Stack 
6. Design and Architecture
7. Contribution Rules


## 1. Features 
- **Url Shortening and Redirection:** URLs are mapped to a shorter version using Snowflake IDs and Base62 encoding for unique, compact links. Users can then use these short links to be redirected to the original URL.
- **Url Analytics Tracking**: We track the number of times a URL is clicked. Clicks are cached in Redis to reduce write load on the Cassandra database, ensuring high performance.
- **User Authentication:** Users can sign up to create and manage their own links. The system uses session-based authentication, password hashing with Argon2, and role-based access control to ensure security and proper resource management.
- **Url Customization:** Urls can be password protected and can be toggled as "active" or "inactive". Essentially an inactive link won't redirect you, akin to a private youtube video. These attributes can only be controlled by the user who created the url, reinforcing proper access control.


## 2. Getting Started
- **Prerequisites:**
  - [Install Astral UV](https://docs.astral.sh/uv/getting-started/installation/)
  - [Install Docker](https://docs.docker.com/engine/install/)
  -  `make` build automation tool to run `Makefile`
- **Installation:**
```bash
# Clone 
git clone https://github.com/Knguyen-dev/url-shortener.git

cd url-shortener

# Install backend dependencies
cd backend && uv sync
```
- **Configuration:** Setup a `.env.dev` file with the below contents.
```bash
# Simple Postgres Setup
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=postgres 
POSTGRES_USER=dev
POSTGRES_PASSWORD=devpass

# Cassandra; Cassandra by default often uses <username:password> as "cassandra:cassandra"
CASSANDRA_HOST=cassandra
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=urlshortener
CASSANDRA_CLUSTER_NAME=UrlShortenerCluster
CASSANDRA_DC=dc1
CASSANDRA_RACK=rack1
CASSANDRA_ENDPOINT_SNITCH=GossipingPropertyFileSnitch

# Redis Setup
REDIS_URL=redis://redis:6379/0
REDIS_HOST="redis"
REDIS_PORT=6379
REDIS_DB=0

# App-related Env
ENVIRONMENT="development" 
```

## 3. Usage

- Ensure Docker daemon is running.
```bash
# Start up the application
make up

# Shut down the application
make down
```
The application is forwarded to port 8000 of your local machine. You can find and control this through the `Dockerfile` and `docker-compose.dev.yaml`.

### Project Scripts
All of the commands needed to run the application are available in `Makefile`. However I'll explain them here:
- `make up`: Used to start all containers for the application. This is how you start the application for the first time.
- `make down`: Shuts down the API only. This is useful because mainly in this application, you'll notice that you're mostly starting/stopping the API, rather than everything. Typically you want to avoid shutting down and spinning everything up since that can take about 23 seconds. This is mainly due to how Cassandra takes a long time to startup.
- `make down-all`: Shuts down all containers.
- `make clean`: Shuts down all containers and destroys all existing volumes. This is mainly used when you want to reset the databases. For example, if you've made a schema change in postgres or cassandra, you'll need to destroy the existing volumes containing your current schema, to make room for our new schema. Then you'd do `make up` to start the application from a clean state. Note that this can take an upwards of 70-80 seconds due to Cassandra taking a long time to start up from a blank slate. But after everything is setup, spinning up the application should take a shorter amount of time.
- `make restart`: Essentially restarts the web application only. This is because it shuts down the web application only and turns everything on again. However, usually you'll already have your postgres, redis, and cassandra containers already running, so only your web app is spun up again. This is quite efficient.
- `make logs`: Lets you see the real time logs for the web application. You'll use this extensively to see the application's state, any errors, what's hitting, etc.
- `make logs-all`: Let's you see real time logs for all containers at once. You won't use this much, but I kept this in just in case.
- `make shell`: Shells you into the web application. 
- `make psql`: Shells you into the Postgres container. You'll mainly use this to see the data contained in there.
- `make cql`: Shells you into the Cassandra container and automatically puts you in the `urlshortener` keyspace. Make sure the keyspace name matches whatever your put in your `.env.dev` file. You'll use this to see the data contained in your Cassandra keyspace
- `make lint`: Lints the backend, running style checks and fixing them. You'll run this to clean up the code before committing or pushing.
- `make format`: Formats the backend code. You'll run this before committing.
- `make test:` Runs any tests in the backend.
- `make frontend`: If you ever make a frontend in the future, you'll use something like this to run the frontend without spinning up the backend. This would allow for quick frontend development and iteration. 

## 4. API Reference

You can find documentation for the API at `localhost:8000/docs` or just the `/docs` route of where the API runs. This uses FastAPI's builtin documentation feature that documents all of the endpoints and the data models/schemas that are used for requests bodies, parameters, and response models. I also recommend cross-referencing with the `types.py` file which will add more developer details and design decisions for particular data models.

## 5. Technical Stack 
- **Python, FastAPI:** Uses FastAPI framework to develop our python-based API. This just makes things modern, easier to maintain, and allows for fast development.
- **Postgres:** Used for storing authentication-related data (e.g., users and sessions) due to its high data consistency and integrity, which is essential for sensitive information. We also use database connection pooling to optimize performance.
- **Cassandra:** Utilized for storing URL data, including the number of clicks. Its high write performance and distributed P2P architecture are ideal for an application designed to scale horizontally, have high availability, and handle a large number of redirects efficiently.
- **Redis:** An in-memory cache used to cache URL clicks, reducing write load on the Cassandra database. It is also used for session-based caching to minimize database queries for user sessions.


## 6. Design and Architecture 

### Database and Application Diagrams
[Url Shortener's Diagrams](https://lucid.app/lucidchart/b0dfd4d3-202d-4f52-845f-750ae04a93e1/edit?viewport_loc=759%2C-232%2C3100%2C1208%2C0_0&invitationId=inv_911a3eee-8815-40b8-8e87-ecf174111ab1)

You can find the diagrams for the postgres schema, cassandra keyspace, and application architecture on that link. In general though, it should be pretty straight forward to re-create the database diagrams, and the architecture of the application itself isn't that complex.

### Postgres Schema Design 
**`users` table**
- `id`: Id of the user, the PK.
- `email`: Email of the user, which has to be unique.
- `full_name`: Full name of the user.
- `is_admin`: Boolean indicating whether the user is an admin.
- `password_hash`: The password hash associated with the user's account.
- `created_at`: When the user's account was created.

Overall this is a pretty standard and straightforward design.

**`sessions` table**
- `user_id`: Id of the user that's associated with the session.
- `session_token`: A cryptographically secure string that uniquely identifies a session.
- `created_at`: When the session was created at. This is also used to calculate when a session is expired. You could also use an `expires_at` field.
- `last_active_at`: This keeps track of the last time the user made an authenticated request. This is how applications can have features like an idle timeout. For example, the last time the user made an authenticated request was over an hour ago, reject them.

### Cassandra Schema Design
Remember that Cassandra uses a query-first philosophy, so each table here satisfies a specific query we had in mind.

**`url_by_backhalf_alias` table**
This table is designed precisely for when we need to query the database our redirection routes. It is also used when we have to update some properties of the url.
- `backhalf_alias`: The short hash that uniquely identifies each shortened url in the table.
- `user_id`: Id of the user who created the url, which maps to a key in a postgres.
- `original_url`: The original url that this maps to.
- `password_hash`: The password hash if this url is password-protected. Else nulled when it's not.
- `is_active`: A boolean indicating whether or not the url is active. If the url isn't active, we will prevent redirects to it.

The primary key here is just the `backhalf_alias` as that's the sole value that the redirect endpoints are going to receive and query our database by.

**`url_by_user_id` table**
This table is designed for when we need to render a user dashboard, and show all of the links that a given user has created. It's also used when we have to update a url's properties.
- `user_id`: Id of the user who created the url.
- `backhalf_alias`: Shortened alias.
- `original_url`: The short hash that uniquely identifies the ID in the `url_by_backhalf_alias` table.
- `is_active`: Whether the url is active or not.
- `title`: The title of the url.
- `created_at`: When the url was created.

We have a composite primary key, ensuring that each `user_id` can have multiple backhalf_alias entries, and that each (user_id, backhalf_alias) pair is unique. This allows us to query all urls for a given user, and even narrow down the search to a single url for a given user.

**`url_clicks_by_backhalf_alias` table**
- `backhalf_alias`: The shortened alias.
- `total_clicks`: The total amount of times this url has been clicked.

In distributed systems, keeping an accurate count is a little more complex and requires more work. As a result, Cassandra forces us to use have a separate table containing the clicks for a url. Here the primary key is the `backhalf_alias`. 

### Infrastructure and Production Practices
- **Logging:** Structured logging for production including essential details like timestamp, endpoint, and IP address.
- **CI/CD:** A CI/CD pipeline with GitHub Actions that automates code quality checks, building, and deployment of the built image to GHCR.
- **Docker-based Development:** Uses Docker and `Makefile` to create a consistent, repeatable development environment.for all dependencies.
- **Microservices-ready:** The system is designed to be easily transitioned into a distributed system. This is evident as it leverages Cassandra (distributed database), and the alias generation has been prepared to scale up to multiple machines. As well as this, the session caching with Redis allows for a centralized session store for multiple machines.

## 7. Contributions
Any and all contributions are welcome! If you'd like to contribute, please create a feature branch and ideally target an issue that's already listed in the repository.

## Credits
- [URL Shortener - System Design School](https://systemdesignschool.io/problems/url-shortener/solution)
- [Redis.py Docs](https://redis.readthedocs.io/en/stable/commands.html)