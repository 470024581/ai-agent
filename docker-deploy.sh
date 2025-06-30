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

# Deployment mode selection
echo ""
echo "📋 Deployment Options:"
echo "1. Separated Services (Frontend + Backend) - Recommended for development"
echo "2. Combined Service (All-in-one) - Simpler for production"

read -p "Please select deployment mode (1/2) [default: 1]: " deploy_mode
deploy_mode=${deploy_mode:-1}

# Create necessary data directories based on mode
echo ""
print_info "Creating Docker data directories..."

if [ "$deploy_mode" = "1" ]; then
    directories=(
        "docker_data"
        "docker_data/app_data"
        "docker_data/embeddings_cache"
    )
    data_path="docker_data"
else
    directories=(
        "docker_data_combined"
        "docker_data_combined/app_data"
        "docker_data_combined/embeddings_cache"
    )
    data_path="docker_data_combined"
fi

for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_success "Created directory: $dir"
    else
        print_info "Directory already exists: $dir"
    fi
done

# Set permissions
chmod -R 755 $data_path/
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

case $deploy_mode in
    1)
        print_info "Building separated frontend and backend services..."
        $DOCKER_COMPOSE build frontend backend
        if [ $? -ne 0 ]; then
            print_error "Build failed"
            exit 1
        fi
        
        print_info "Starting separated services..."
        $DOCKER_COMPOSE up -d frontend backend
        if [ $? -ne 0 ]; then
            print_error "Service startup failed"
            exit 1
        fi
        
        # Wait for services to start
        echo ""
        print_info "Waiting for services to start..."
        sleep 15
        
        # Check service status
        echo ""
        print_info "Checking service status..."
        
        if $DOCKER_COMPOSE ps | grep -q "ai-agent-frontend.*Up"; then
            print_success "Frontend service is running normally"
        else
            print_error "Frontend service startup failed"
            print_info "View logs: $DOCKER_COMPOSE logs frontend"
        fi
        
        if $DOCKER_COMPOSE ps | grep -q "ai-agent-backend.*Up"; then
            print_success "Backend service is running normally"
        else
            print_error "Backend service startup failed"
            print_info "View logs: $DOCKER_COMPOSE logs backend"
            exit 1
        fi
        
        # Display service information
        echo ""
        echo "🎉 Separated Services Deployment Complete!"
        echo ""
        print_info "Service Information:"
        echo "  - Frontend URL: http://localhost:3000"
        echo "  - Backend API: http://localhost:8000"
        echo "  - API Documentation: http://localhost:8000/docs"
        echo "  - Health Check: http://localhost:8000/health"
        
        ;;
    2)
        print_info "Building combined AI Agent application..."
        $DOCKER_COMPOSE --profile combined build ai-agent
        if [ $? -ne 0 ]; then
            print_error "Build failed"
            exit 1
        fi
        
        print_info "Starting combined service..."
        $DOCKER_COMPOSE --profile combined up -d ai-agent
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
            print_success "AI Agent combined service is running normally"
        else
            print_error "AI Agent service startup failed"
            print_info "View logs: $DOCKER_COMPOSE logs ai-agent"
            exit 1
        fi
        
        # Display service information
        echo ""
        echo "🎉 Combined Service Deployment Complete!"
        echo ""
        print_info "Service Information:"
        echo "  - Application URL: http://localhost:8080"
        echo "  - API Documentation: http://localhost:8080/docs"
        echo "  - Health Check: http://localhost:8080/health"
        
        ;;
    *)
        print_error "Invalid option"
        exit 1
        ;;
esac

# Verify deployment
echo ""
print_info "Verifying deployment..."

# Check health status based on mode
if [ "$deploy_mode" = "1" ]; then
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Backend health check passed"
    else
        print_warning "Backend health check failed, service may still be starting"
    fi
    
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        print_success "Frontend health check passed"
    else
        print_warning "Frontend health check failed, service may still be starting"
    fi
else
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        print_success "Application health check passed"
    else
        print_warning "Application health check failed, service may still be starting"
    fi
fi

echo ""
print_info "Common Commands:"
if [ "$deploy_mode" = "1" ]; then
    echo "  View service status: $DOCKER_COMPOSE ps"
    echo "  View frontend logs: $DOCKER_COMPOSE logs -f frontend"
    echo "  View backend logs: $DOCKER_COMPOSE logs -f backend"
    echo "  Stop services: $DOCKER_COMPOSE down"
    echo "  Restart services: $DOCKER_COMPOSE restart frontend backend"
else
    echo "  View service status: $DOCKER_COMPOSE --profile combined ps"
    echo "  View logs: $DOCKER_COMPOSE --profile combined logs -f ai-agent"
    echo "  Stop service: $DOCKER_COMPOSE --profile combined down"
    echo "  Restart service: $DOCKER_COMPOSE --profile combined restart ai-agent"
fi

echo ""
print_info "Data Persistence:"
echo "  Application data: ./$data_path/app_data"
echo "  Embedding cache: ./$data_path/embeddings_cache"

echo ""
print_warning "⚠️  Important Reminders:"
echo "  1. Please ensure the OpenAI API key is correctly configured in the .env file"
echo "  2. Change the SECRET_KEY in production environment"
echo "  3. Backup the $data_path directory for data persistence"

echo ""
print_success "AI Agent Docker deployment completed! 🎊" 