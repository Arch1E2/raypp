#!/bin/bash

# Test script for RayPP API
# This script tests all the main endpoints to verify the setup

echo "========================================="
echo "RayPP API Test Script"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to test endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local method=${3:-GET}
    local data=$4
    
    echo -n "Testing $name... "
    
    if [ "$method" = "POST" ]; then
        response=$(curl -s -X POST "$url" -H "Content-Type: application/json" -d "$data" -w "\n%{http_code}")
    else
        response=$(curl -s "$url" -w "\n%{http_code}")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED (HTTP $http_code)${NC}"
        echo "Response: $body"
        ((FAILED++))
    fi
}

# Run tests
echo "1. Health Check Tests"
echo "---------------------"
test_endpoint "Root endpoint" "http://localhost:8000/"
test_endpoint "General health" "http://localhost:8000/api/health"
test_endpoint "PostgreSQL health" "http://localhost:8000/api/health/postgres"
test_endpoint "Redis health" "http://localhost:8000/api/health/redis"
test_endpoint "ChromaDB health" "http://localhost:8000/api/health/chromadb"
echo ""

echo "2. PostgreSQL Operations"
echo "------------------------"
test_endpoint "Create item" "http://localhost:8000/api/items" "POST" '{"name":"Test Item","description":"A test item"}'
test_endpoint "Get items" "http://localhost:8000/api/items"
echo ""

echo "3. Redis Cache Operations"
echo "--------------------------"
test_endpoint "Set cache" "http://localhost:8000/api/cache/test_key?value=test_value&ttl=60" "POST"
test_endpoint "Get cache" "http://localhost:8000/api/cache/test_key"
echo ""

echo "4. ChromaDB Vector Operations"
echo "------------------------------"
test_endpoint "Add vectors" "http://localhost:8000/api/vectors/add" "POST" '{"collection_name":"test","documents":["Hello","World"],"ids":["1","2"]}'
test_endpoint "Query vectors" "http://localhost:8000/api/vectors/query" "POST" '{"collection_name":"test","query_texts":["Hello"],"n_results":2}'
echo ""

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please check the output above.${NC}"
    exit 1
fi
