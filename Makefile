COMPOSE_FILE=docker-compose.dev.yaml
PROJECT_NAME=url-shortener
WEB_SERVICE_NAME=web

.PHONY: up down restart logs shell frontend 

# Startup project in dev environment. 
up:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) up --build -d 

# Shut down the webapp
down:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) stop $(WEB_SERVICE_NAME)

# Shut down all containers
down-all:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) down

# Shut down the app and clear all data!
# Note: Probably good if you want to clear all existing data
clean:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) down -v

# Restart the application
restart: down up

# Show the real-time logs for the web service
logs:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) logs -f $(WEB_SERVICE_NAME)

logs-all:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) logs -f

# For execing into the container
shell:
	@docker exec -it $(shell docker ps -q -f "name=$(PROJECT_NAME)-web") /bin/sh

psql:
	@docker exec -it $(PROJECT_NAME)-postgres-1 psql -U dev -d postgres

# Lints and fixes common linting errors
# Note: Remove --fix flag if you just want to see the errors. 
lint:
	# Checks for and fixes simple linting errors
	@cd backend && uv run ruff check --fix .

# Formats code files
# Note: Use the --check flag to see what files are fixed.
format:
	@cd backend && uv run ruff format .

# ===============================
# Cassandra Helper Commands
# ===============================
# In cqlsh:
#   SELECT * FROM url_by_backhalf_alias;
# 	SELECT * FROM url_by_user_id;
#   SELECT * FROM url_clicks_by_backhalf_alias;
#
#   DELETE FROM url_by_backhalf_alias;
#   TRUNCATE url_by_backhalf_alias;
#
#   List all keyspaces:
#       DESCRIBE KEYSPACES;
#
#   Select a keyspace:
#       USE my_keyspace;
#
#   List all tables in the current keyspace:
#       DESCRIBE TABLES;
#
#   Inspect a specific table's schema:
#       DESCRIBE TABLE my_table;
#
#   View table data:
#       SELECT * FROM my_table LIMIT 20;
#
#   Exit:
#       EXIT;
# ===============================
cql: 	
	@docker exec -it $(PROJECT_NAME)-cassandra-1 cqlsh -k urlshortener
	
redis:
	@docker exec -it $(PROJECT_NAME)-redis-1 redis-cli

frontend:
	cd frontend && npm run dev
