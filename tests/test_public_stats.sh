#!/bin/bash

# Source utils
source "$(dirname "$0")/utils.sh"

test_public_stats() {
    echo "Testing public_stats endpoints..."

    # Test successful response
    response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/public_stats/")
    status=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n1)

    if [ "$status" -eq 200 ]; then
        echo -e "${GREEN}✓${NC} Public stats returns 200"
        
        # Validate JSON structure
        if echo "$body" | jq -e '.timestamp and .total_jobs and .main_chat_jobs and .individual_crew_jobs and .top_profile_stacks_addresses and .top_crew_names' >/dev/null; then
            echo -e "${GREEN}✓${NC} Response structure is valid"
        else
            echo -e "${RED}✗${NC} Invalid response structure"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
        
        # Validate timestamp format
        if echo "$body" | jq -e '.timestamp | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")' >/dev/null; then
            echo -e "${GREEN}✓${NC} Timestamp format is valid"
        else
            echo -e "${RED}✗${NC} Invalid timestamp format"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
        
        # Validate arrays
        if echo "$body" | jq -e '.top_profile_stacks_addresses | type == "array"' >/dev/null && \
           echo "$body" | jq -e '.top_crew_names | type == "array"' >/dev/null; then
            echo -e "${GREEN}✓${NC} Arrays are present and valid"
        else
            echo -e "${RED}✗${NC} Invalid array structure"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
        
    else
        echo -e "${RED}✗${NC} Public stats should return 200, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 4))

    # Test CORS headers
    test_cors "/public_stats/" "Public stats CORS"
}
