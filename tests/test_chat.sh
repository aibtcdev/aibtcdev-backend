#!/bin/bash

# Source utils
source "$(dirname "$0")/utils.sh"

# Mock JWT token for testing
VALID_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIn0.1234567890"

test_chat() {
    echo "Testing chat endpoints..."

    # Test create thread endpoint
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/chat/threads")
    status=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n1)
    
    if [ "$status" -eq 500 ]; then
        echo -e "${GREEN}✓${NC} Create thread returns 500 for error case"
    else
        echo -e "${RED}✗${NC} Create thread should return 500 for error case, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test get threads endpoint
    response=$(curl -s -w "\n%{http_code}" -X GET \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/chat/threads")
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 500 ]; then
        echo -e "${GREEN}✓${NC} Get threads returns 500 for error case"
    else
        echo -e "${RED}✗${NC} Get threads should return 500 for error case, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test get latest thread endpoint
    response=$(curl -s -w "\n%{http_code}" -X GET \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/chat/threads/latest")
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 500 ]; then
        echo -e "${GREEN}✓${NC} Get latest thread returns 500 for error case"
    else
        echo -e "${RED}✗${NC} Get latest thread should return 500 for error case, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test chat trigger endpoint
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $VALID_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"input_str":"test message"}' \
        "${API_URL}/chat/?thread_id=123")
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 500 ]; then
        echo -e "${GREEN}✓${NC} Chat trigger returns 500 for error case"
    else
        echo -e "${RED}✗${NC} Chat trigger should return 500 for error case, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test stream endpoint with invalid job ID
    response=$(curl -s -w "\n%{http_code}" -X GET \
        "${API_URL}/chat/invalid-uuid/stream")
    status=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n1)
    
    if echo "$body" | grep -q "Task not found"; then
        echo -e "${GREEN}✓${NC} Stream endpoint returns error for invalid job ID"
    else
        echo -e "${RED}✗${NC} Stream endpoint should return error for invalid job ID"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test delete thread endpoint
    response=$(curl -s -w "\n%{http_code}" -X DELETE \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/chat/threads/123")
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 500 ]; then
        echo -e "${GREEN}✓${NC} Delete thread returns 500 for error case"
    else
        echo -e "${RED}✗${NC} Delete thread should return 500 for error case, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test CORS headers for all endpoints
    test_cors "/chat/threads" "Chat threads CORS"
    test_cors "/chat/threads/latest" "Chat latest thread CORS"
    test_cors "/chat/" "Chat trigger CORS"
}
