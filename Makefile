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

shell-postgres:
	@docker exec -it url-shortener-postgres-1 psql -U dev -d postgres

frontend:
	cd frontend && npm run dev
