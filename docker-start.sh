#!/bin/bash

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "docker-compose is not installed. Please install Docker and docker-compose first."
    exit 1
fi

# Function to display usage
show_usage() {
    echo "Usage: ./docker-start.sh [OPTION]"
    echo "Options:"
    echo "  up        Start the application (default)"
    echo "  down      Stop the application"
    echo "  rebuild   Rebuild and start the application"
    echo "  logs      Show application logs"
    echo "  shell     Open a shell in the running container"
    echo "  help      Show this help message"
}

# Process command line arguments
case "$1" in
    up|"")
        echo "Starting WhatTheCV in Docker..."
        docker-compose up -d
        echo "Application is running at http://localhost:8000"
        ;;
    down)
        echo "Stopping WhatTheCV..."
        docker-compose down
        ;;
    rebuild)
        echo "Rebuilding and starting WhatTheCV..."
        docker-compose down
        docker-compose build
        docker-compose up -d
        echo "Application is running at http://localhost:8000"
        ;;
    logs)
        echo "Showing logs for WhatTheCV..."
        docker-compose logs -f
        ;;
    shell)
        echo "Opening shell in the container..."
        docker-compose exec app /bin/bash
        ;;
    help)
        show_usage
        ;;
    *)
        echo "Unknown option: $1"
        show_usage
        exit 1
        ;;
esac 