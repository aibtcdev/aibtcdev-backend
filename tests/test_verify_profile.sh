#!/bin/bash

# Source utils
source "$(dirname "$0")/utils.sh"

# Mock JWT token for testing
VALID_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIn0.1234567890"
INVALID_TOKEN="invalid.token.format"

test_verify_profile() {
    echo "Testing verify_profile endpoints..."

    # Test without authorization header
    response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/verify")
    status=$(echo "$response" | tail -n1)
    if [ "$status" -eq 401 ]; then
        echo -e "${GREEN}✓${NC} Missing auth header returns 401"
    else
        echo -e "${RED}✗${NC} Missing auth header should return 401, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test with invalid token format
    response=$(curl -s -w "\n%{http_code}" -X GET \
        -H "Authorization: Bearer $INVALID_TOKEN" \
        "${API_URL}/verify")
    status=$(echo "$response" | tail -n1)
    if [ "$status" -eq 401 ]; then
        echo -e "${GREEN}✓${NC} Invalid token format returns 401"
    else
        echo -e "${RED}✗${NC} Invalid token should return 401, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test with valid token format but non-existent user
    response=$(curl -s -w "\n%{http_code}" -X GET \
        -H "Authorization: Bearer $VALID_TOKEN" \
        "${API_URL}/verify")
    status=$(echo "$response" | tail -n1)
    if [ "$status" -eq 404 ]; then
        echo -e "${GREEN}✓${NC} Non-existent user returns 404"
    else
        echo -e "${RED}✗${NC} Non-existent user should return 404, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test CORS headers
    test_cors "/verify" "Verify profile CORS"
}
