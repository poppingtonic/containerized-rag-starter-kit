#!/bin/bash
set -e

echo "================================================"
echo "Knowledge System Integration Tests"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose not found${NC}"
    exit 1
fi

# Function to wait for service
wait_for_service() {
    local service_name=$1
    local service_url=$2
    local max_attempts=30
    local attempt=0

    echo -n "Waiting for $service_name..."

    while [ $attempt -lt $max_attempts ]; do
        if curl -f -s -o /dev/null "$service_url"; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo -e " ${RED}✗${NC}"
    echo -e "${RED}Error: $service_name did not become ready${NC}"
    return 1
}

echo "Step 1: Starting services..."
echo "------------------------------"
docker-compose up -d --build knowledge-system

echo ""
echo "Step 2: Waiting for services to be ready..."
echo "------------------------------"

# Wait for database
wait_for_service "Database" "http://localhost:5433" || exit 1

# Wait for API service
wait_for_service "API Service" "http://localhost:8000/health" || exit 1

# Wait for ingestion service
wait_for_service "Ingestion Service" "http://localhost:5050/status" || exit 1

# Wait for knowledge system
wait_for_service "Knowledge System" "http://localhost:8100/health" || exit 1

echo ""
echo "Step 3: Checking service health..."
echo "------------------------------"

# Check Knowledge System health
echo -n "Knowledge System health check..."
HEALTH=$(curl -s http://localhost:8100/health | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "error")

if [ "$HEALTH" = "healthy" ] || [ "$HEALTH" = "degraded" ]; then
    echo -e " ${GREEN}✓ $HEALTH${NC}"
else
    echo -e " ${RED}✗ unhealthy${NC}"
    echo "Health response:"
    curl -s http://localhost:8100/health | python3 -m json.tool
    exit 1
fi

echo ""
echo "Step 4: Running integration tests..."
echo "------------------------------"

# Install test dependencies if needed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo "Installing test dependencies..."
    pip install -q pytest pytest-asyncio aiohttp
fi

# Set environment variables for tests
export KNOWLEDGE_SYSTEM_URL=http://localhost:8100
export API_SERVICE_URL=http://localhost:8000
export INGESTION_SERVICE_URL=http://localhost:5050

# Run tests
echo ""
if pytest tests/integration/test_knowledge_system.py -v --tb=short; then
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}✓ All integration tests passed!${NC}"
    echo -e "${GREEN}================================================${NC}"
    TEST_RESULT=0
else
    echo ""
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}✗ Some integration tests failed${NC}"
    echo -e "${RED}================================================${NC}"
    TEST_RESULT=1
fi

echo ""
echo "Step 5: Service logs (last 20 lines)..."
echo "------------------------------"
echo ""
echo "Knowledge System logs:"
docker-compose logs --tail=20 knowledge-system

echo ""
echo "================================================"
echo "Test Summary"
echo "================================================"
echo ""
echo "Services running:"
echo "  • Database:          http://localhost:5433"
echo "  • API Service:       http://localhost:8000"
echo "  • Ingestion Service: http://localhost:5050"
echo "  • Knowledge System:  http://localhost:8100"
echo "  • Frontend:          http://localhost:8080"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f knowledge-system"
echo ""

exit $TEST_RESULT
