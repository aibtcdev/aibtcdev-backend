#!/bin/bash

# Source utils
source "$(dirname "$0")/utils.sh"

# Mock JWT token for testing
VALID_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIn0.1234567890"

test_crew() {
    echo "Testing crew endpoints..."

    # Test GET /crew/public endpoint
    response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/crew/public")
    body=$(echo "$response" | head -n1)
    status=$(echo "$response" | tail -n1)

    if [ "$status" -eq 200 ]; then
        # Validate JSON array structure
        if echo "$body" | jq -e 'type == "array"' >/dev/null; then
            echo -e "${GREEN}✓${NC} Public crews returns valid array"
        else
            echo -e "${RED}✗${NC} Invalid public crews response structure"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo -e "${RED}✗${NC} Public crews should return 200, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test GET /crew/tools endpoint
    response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/crew/tools")
    body=$(echo "$response" | head -n1)
    status=$(echo "$response" | tail -n1)

    if [ "$status" -eq 200 ]; then
        # Validate JSON object structure
        if echo "$body" | jq -e 'type == "object"' >/dev/null; then
            echo -e "${GREEN}✓${NC} Tools list returns valid object"
        else
            echo -e "${RED}✗${NC} Invalid tools list response structure"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo -e "${RED}✗${NC} Tools list should return 200, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test POST /crew/{crew_id} without auth
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d '{"input_str":"test input"}' \
        "${API_URL}/crew/1")
    status=$(echo "$response" | tail -n1)

    if [ "$status" -eq 401 ]; then
        echo -e "${GREEN}✓${NC} Crew execution without auth returns 401"
    else
        echo -e "${RED}✗${NC} Crew execution without auth should return 401, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test GET /crew/jobs without auth
    response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/crew/jobs")
    status=$(echo "$response" | tail -n1)

    if [ "$status" -eq 401 ]; then
        echo -e "${GREEN}✓${NC} Jobs list without auth returns 401"
    else
        echo -e "${RED}✗${NC} Jobs list without auth should return 401, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test GET /crew/jobs/{job_id}/stream with invalid job_id
    response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/crew/jobs/invalid-id/stream")
    body=$(echo "$response" | head -n1)
    status=$(echo "$response" | tail -n1)

    if echo "$body" | grep -q "Task not found"; then
        echo -e "${GREEN}✓${NC} Invalid job stream returns error message"
    else
        echo -e "${RED}✗${NC} Invalid job stream should return error message"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test DELETE /crew/jobs/{job_id}/cancel without auth
    response=$(curl -s -w "\n%{http_code}" -X DELETE "${API_URL}/crew/jobs/test-id/cancel")
    status=$(echo "$response" | tail -n1)

    if [ "$status" -eq 401 ]; then
        echo -e "${GREEN}✓${NC} Job cancellation without auth returns 401"
    else
        echo -e "${RED}✗${NC} Job cancellation without auth should return 401, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test CORS headers for all endpoints
    test_cors "/crew/public" "Public crews CORS"
    test_cors "/crew/tools" "Tools list CORS"
    test_cors "/crew/1" "Crew execution CORS"
    test_cors "/crew/jobs" "Jobs list CORS"
    test_cors "/crew/jobs/test-id/stream" "Job stream CORS"
    test_cors "/crew/jobs/test-id/cancel" "Job cancellation CORS"
}
