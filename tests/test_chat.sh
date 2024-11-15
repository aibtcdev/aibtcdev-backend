#!/bin/bash

# Source utils
source "$(dirname "$0")/utils.sh"

# Mock JWT token for testing
VALID_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIn0.1234567890"

test_chat() {
    echo "Testing chat endpoints..."

    # Test create conversation endpoint
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/chat/conversations")
    status=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n1)
    
    if [ "$status" -eq 404 ]; then
        echo -e "${GREEN}✓${NC} Create conversation returns 404 for non-existent user"
    else
        echo -e "${RED}✗${NC} Create conversation should return 404 for non-existent user, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test get conversations endpoint
    response=$(curl -s -w "\n%{http_code}" -X GET \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/chat/conversations")
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 404 ]; then
        echo -e "${GREEN}✓${NC} Get conversations returns 404 for non-existent user"
    else
        echo -e "${RED}✗${NC} Get conversations should return 404 for non-existent user, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test get latest conversation endpoint
    response=$(curl -s -w "\n%{http_code}" -X GET \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/chat/conversations/latest")
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 404 ]; then
        echo -e "${GREEN}✓${NC} Get latest conversation returns 404 for non-existent user"
    else
        echo -e "${RED}✗${NC} Get latest conversation should return 404 for non-existent user, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test chat trigger endpoint
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $VALID_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"input_str":"test message"}' \
        "${API_URL}/chat/?conversation_id=123")
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 404 ]; then
        echo -e "${GREEN}✓${NC} Chat trigger returns 404 for non-existent user"
    else
        echo -e "${RED}✗${NC} Chat trigger should return 404 for non-existent user, got $status"
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

    # Test delete conversation endpoint
    response=$(curl -s -w "\n%{http_code}" -X DELETE \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/chat/conversations/123")
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 404 ]; then
        echo -e "${GREEN}✓${NC} Delete conversation returns 404 for non-existent user"
    else
        echo -e "${RED}✗${NC} Delete conversation should return 404 for non-existent user, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test CORS headers for all endpoints
    test_cors "/chat/conversations" "Chat conversations CORS"
    test_cors "/chat/conversations/latest" "Chat latest conversation CORS"
    test_cors "/chat/" "Chat trigger CORS"
}
