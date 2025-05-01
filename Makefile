.PHONY: setup start docker-up docker-down docker-logs docker-rebuild migrate

# Local development commands
setup:
	./run.sh setup

start:
	./run.sh start

# Docker commands
docker-up:
	./docker-start.sh up

docker-down:
	./docker-start.sh down

docker-logs:
	./docker-start.sh logs

docker-rebuild:
	./docker-start.sh rebuild

docker-shell:
	./docker-start.sh shell

# Database migration
migrate:
	python -m app.db.migrations.add_supabase_id

# Help
help:
	@echo "WhatTheCV Backend Makefile"
	@echo "--------------------------"
	@echo "setup         - Set up local development environment"
	@echo "start         - Start the application locally"
	@echo "docker-up     - Start the application in Docker"
	@echo "docker-down   - Stop the Docker containers"
	@echo "docker-logs   - View Docker logs"
	@echo "docker-rebuild - Rebuild and restart Docker containers"
	@echo "docker-shell  - Access shell in the Docker container"
	@echo "migrate       - Run database migrations"

# Default target
default: help 