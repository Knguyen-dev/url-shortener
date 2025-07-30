COMPOSE_FILE=docker-compose.dev.yaml
PROJECT_NAME=url-shortener

.PHONY: up down restart logs shell frontend 

# Startup project in dev environment. 
up:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) up --build -d 

# Shut down the webapp
down:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) stop web

# Shut down all containers
down-all:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) down


# Shut down the app and clear all data!
# Note: Probably good if you want to clear all existing data
clean:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) down -v

# Restart the application
restart: down up

# Show the real-time logs for the container
logs:
	@docker compose -f $(COMPOSE_FILE) -p $(PROJECT_NAME) logs -f

# For execing into the container
shell:
	@docker exec -it $(shell docker ps -q -f "name=$(PROJECT_NAME)-web") /bin/sh

frontend:
	cd frontend && npm run dev
