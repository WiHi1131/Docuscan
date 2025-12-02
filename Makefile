# Makefile for DocuScan project

.PHONY: help setup build start stop logs test clean deploy

# Default target
help:
	@echo "DocuScan - Available Commands:"
	@echo ""
	@echo "  make setup        - Set up local development environment"
	@echo "  make build        - Build Docker images"
	@echo "  make start        - Start all services"
	@echo "  make stop         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - View logs (all services)"
	@echo "  make logs-api     - View API logs"
	@echo "  make logs-worker  - View worker logs"
	@echo "  make test         - Run tests"
	@echo "  make clean        - Clean up containers and volumes"
	@echo "  make deploy       - Deploy to Google Cloud"
	@echo "  make shell-api    - Open shell in API container"
	@echo "  make shell-worker - Open shell in worker container"
	@echo "  make db-shell     - Connect to PostgreSQL"
	@echo "  make redis-shell  - Connect to Redis"
	@echo ""

# Setup local environment
setup:
	@echo "Setting up local environment..."
	./setup-local.sh

# Build Docker images
build:
	@echo "Building Docker images..."
	docker-compose build

# Start services
start:
	@echo "Starting services..."
	docker-compose up -d
	@echo "Services started. API available at http://localhost:8080"

# Stop services
stop:
	@echo "Stopping services..."
	docker-compose down

# Restart services
restart: stop start

# View logs
logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v

# Clean up
clean:
	@echo "Cleaning up..."
	docker-compose down -v
	rm -rf local-storage/*
	@echo "Cleanup complete"

# Deploy to GCP
deploy:
	@echo "Deploying to Google Cloud..."
	cd infrastructure && ./deploy.sh

# Open shell in containers
shell-api:
	docker-compose exec api /bin/bash

shell-worker:
	docker-compose exec worker /bin/bash

# Database shell
db-shell:
	docker-compose exec postgres psql -U postgres -d docuscan

# Redis shell
redis-shell:
	docker-compose exec redis redis-cli

# Initialize database
init-db:
	@echo "Initializing database..."
	curl -X POST http://localhost:8080/admin/init-db

# Check service health
health:
	@echo "Checking service health..."
	@curl -s http://localhost:8080/health | jq '.'

# Run examples
examples:
	@echo "Running API examples..."
	./examples.sh

# Format code (requires black and isort)
format:
	@echo "Formatting Python code..."
	black api/ worker/ tests/
	isort api/ worker/ tests/

# Lint code (requires flake8)
lint:
	@echo "Linting Python code..."
	flake8 api/ worker/ tests/ --max-line-length=100

# Install dependencies
install:
	pip install -r requirements.txt
	pip install -r requirements-worker.txt
	pip install pytest black isort flake8

# Create test PDF
test-pdf:
	@echo "Creating test PDF..."
	@python3 -c "from reportlab.pdfgen import canvas; c = canvas.Canvas('test.pdf'); c.drawString(100, 750, 'This is a test document for DocuScan OCR'); c.drawString(100, 700, 'Testing text extraction capabilities'); c.save()"
	@echo "test.pdf created"
