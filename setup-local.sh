#!/bin/bash

# DocuScan Local Setup Script
# Sets up local development environment

set -e

echo "=== DocuScan Local Setup ==="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose not found. Please install docker-compose."
    exit 1
fi

echo "✓ Docker is running"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created. Please update with your credentials."
else
    echo "✓ .env file already exists"
fi

# Create local storage directory
mkdir -p local-storage/uploads
mkdir -p local-storage/results
echo "✓ Local storage directories created"

# Pull base images
echo ""
echo "Pulling base Docker images..."
docker-compose pull

# Build services
echo ""
echo "Building DocuScan services..."
docker-compose build

# Start services
echo ""
echo "Starting services..."
docker-compose up -d

# Wait for services to be ready
echo ""
echo "Waiting for services to start..."
sleep 10

# Check service health
echo ""
echo "Checking service health..."

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "✓ PostgreSQL is ready"
else
    echo "✗ PostgreSQL is not ready"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis is ready"
else
    echo "✗ Redis is not ready"
fi

# Check API
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✓ API is ready"
else
    echo "✗ API is not ready yet (may need more time)"
fi

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Services are running:"
echo "  - API: http://localhost:8080"
echo "  - API Docs: http://localhost:8080/docs"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo "  - Pub/Sub Emulator: localhost:8085"
echo ""
echo "Next steps:"
echo "  1. Initialize database: curl -X POST http://localhost:8080/admin/init-db"
echo "  2. Test health: curl http://localhost:8080/health"
echo "  3. View logs: docker-compose logs -f"
echo "  4. Upload a test file: curl -X POST -F 'file=@test.pdf' http://localhost:8080/upload"
echo ""
echo "To stop services: docker-compose down"
echo "To view logs: docker-compose logs -f [service]"
echo ""
