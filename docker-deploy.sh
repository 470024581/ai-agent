#!/bin/bash

# AI Agent Docker Deployment Script
# Usage: chmod +x docker-deploy.sh && ./docker-deploy.sh

set -e

echo "🐳 AI Agent Docker Deployment Script"
echo "===================================="

# Define colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Check Docker and Docker Compose
echo ""
print_info "Checking system requirements..."

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Detect Docker Compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

print_success "Docker and Docker Compose are installed"

# Check current directory
if [ ! -f "docker-compose.yml" ] || [ ! -f "Dockerfile" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

print_info "Current directory: $(pwd)"

# Create necessary data directories
echo ""
print_info "Creating Docker data directories..."

directories=(
    "docker_data"
    "docker_data/app_data"
    "docker_data/embeddings_cache"
)

for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_success "Created directory: $dir"
    else
        print_info "Directory already exists: $dir"
    fi
done

# Set permissions
chmod -R 755 docker_data/
print_success "Set data directory permissions"

# Environment variable configuration
echo ""
print_info "Configuring environment variables..."

if [ ! -f ".env" ]; then
    if [ -f "docker.env.example" ]; then
        cp docker.env.example .env
        print_success "Created environment configuration file: .env (copied from docker.env.example)"
        print_warning "Please edit the .env file to configure your OpenAI API key"
    else
        print_warning "Environment configuration template file not found"
    fi
else
    print_info "Environment configuration file already exists: .env"
fi

# Build and start services
echo ""
print_info "Building and starting Docker services..."

print_info "Building AI Agent application..."
$DOCKER_COMPOSE build ai-agent
if [ $? -ne 0 ]; then
    print_error "Build failed"
    exit 1
fi

print_info "Starting AI Agent service..."
$DOCKER_COMPOSE up -d ai-agent
if [ $? -ne 0 ]; then
    print_error "Service startup failed"
    exit 1
fi

# Wait for service to start
echo ""
print_info "Waiting for service to start..."
sleep 10

# Check service status
echo ""
print_info "Checking service status..."

if $DOCKER_COMPOSE ps | grep -q "ai-agent-app.*Up"; then
    print_success "AI Agent service is running normally"
else
    print_error "AI Agent service startup failed"
    print_info "View logs: $DOCKER_COMPOSE logs ai-agent"
    exit 1
fi

# Verify deployment
echo ""
print_info "Verifying deployment..."

# Check health status
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    print_success "Application health check passed"
else
    print_warning "Application health check failed, service may still be starting"
fi

# Display deployment information
echo ""
echo "🎉 Deployment Complete!"
echo ""
print_info "Service Information:"
echo "  - Application URL: http://localhost:8000"
echo "  - API Documentation: http://localhost:8000/docs"
echo "  - Health Check: http://localhost:8000/health"

echo ""
print_info "Common Commands:"
echo "  View service status: $DOCKER_COMPOSE ps"
echo "  View logs: $DOCKER_COMPOSE logs -f ai-agent"
echo "  Stop service: $DOCKER_COMPOSE down"
echo "  Restart service: $DOCKER_COMPOSE restart ai-agent"

echo ""
print_info "Data Persistence:"
echo "  Application data: ./docker_data/app_data"
echo "  Embedding cache: ./docker_data/embeddings_cache"

echo ""
print_warning "⚠️  Important Reminders:"
echo "  1. Please ensure the OpenAI API key is correctly configured in the .env file"
echo "  2. Change the SECRET_KEY in production environment"
echo "  3. Backup the docker_data directory for data persistence"

echo ""
print_success "AI Agent Docker deployment completed! 🎊" 