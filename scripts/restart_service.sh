#!/bin/bash
#
# Restart GraphRAG Services
# This script allows restarting individual services or the entire stack
#

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR" || { echo "Failed to change to project directory"; exit 1; }

# Available services
SERVICES=(
    "db"
    "ingestion-service"
    "graphrag-processor"
    "api-service"
    "frontend"
    "ocr-service"
    "all"     # Special case for all services
)

# Function to show usage
show_help() {
    echo "Usage: $(basename "$0") [service_name] [--build] [--no-logs]"
    echo ""
    echo "Restart a specific GraphRAG service or all services"
    echo ""
    echo "Available services:"
    printf "  %s\n" "${SERVICES[@]}"
    echo ""
    echo "Options:"
    echo "  --build    Rebuild the service(s) before starting"
    echo "  --no-logs  Don't show logs after restarting"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") graphrag-processor     # Restart GraphRAG processor"
    echo "  $(basename "$0") api-service --build    # Rebuild and restart API service"
    echo "  $(basename "$0") all                    # Restart all services"
    echo ""
}

# Default values
BUILD=""
SHOW_LOGS=true
SERVICE=""

# Parse arguments
for arg in "$@"; do
    case $arg in
        --build)
            BUILD="--build"
            ;;
        --no-logs)
            SHOW_LOGS=false
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            if [[ -z "$SERVICE" ]]; then
                SERVICE="$arg"
            else
                echo "Error: Too many arguments"
                show_help
                exit 1
            fi
            ;;
    esac
done

# Handle no arguments
if [[ -z "$SERVICE" ]]; then
    show_help
    exit 0
fi

# Validate service name
valid_service=false
for svc in "${SERVICES[@]}"; do
    if [[ "$SERVICE" == "$svc" ]]; then
        valid_service=true
        break
    fi
done

if [[ "$valid_service" != true ]]; then
    echo "Error: Invalid service name: $SERVICE"
    echo ""
    show_help
    exit 1
fi

# Function to restart service
restart_service() {
    local service=$1
    echo "Restarting $service..."
    
    if [[ "$service" == "all" ]]; then
        docker-compose down
        docker-compose up -d $BUILD
    else
        docker-compose up -d $BUILD "$service"
    fi
    
    if [[ "$SHOW_LOGS" == true ]]; then
        echo "Displaying logs for $service (press Ctrl+C to exit):"
        if [[ "$service" == "all" ]]; then
            docker-compose logs -f
        else
            docker-compose logs -f "$service"
        fi
    fi
}

# Restart the service
restart_service "$SERVICE"