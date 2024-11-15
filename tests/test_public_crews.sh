#!/bin/bash

# Source utils
source "$(dirname "$0")/utils.sh"

test_public_crews() {
    echo "Testing public_crews endpoints..."

    # Test successful response
    response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/public-crews")
    status=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n1)

    if [ "$status" -eq 200 ]; then
        echo -e "${GREEN}✓${NC} Public crews returns 200"
        
        # Validate JSON structure is an array
        if echo "$body" | jq -e 'type == "array"' >/dev/null; then
            echo -e "${GREEN}✓${NC} Response is a valid array"
            
            # If array is not empty, validate crew structure
            if [ "$(echo "$body" | jq '. | length')" -gt 0 ]; then
                # Check first crew structure
                if echo "$body" | jq -e '.[0] | has("id", "name", "description", "created_at", "creator_email", "agents")' >/dev/null; then
                    echo -e "${GREEN}✓${NC} Crew object structure is valid"
                    
                    # Validate agents array structure if present
                    if echo "$body" | jq -e '.[0].agents | type == "array"' >/dev/null; then
                        if [ "$(echo "$body" | jq '.[0].agents | length')" -gt 0 ]; then
                            if echo "$body" | jq -e '.[0].agents[0] | has("id", "name", "role", "goal", "backstory", "agent_tools", "tasks")' >/dev/null; then
                                echo -e "${GREEN}✓${NC} Agent object structure is valid"
                            else
                                echo -e "${RED}✗${NC} Invalid agent object structure"
                                FAILED_TESTS=$((FAILED_TESTS + 1))
                            fi
                        fi
                    else
                        echo -e "${RED}✗${NC} Invalid agents array"
                        FAILED_TESTS=$((FAILED_TESTS + 1))
                    fi
                    
                    # Verify email masking
                    creator_email=$(echo "$body" | jq -r '.[0].creator_email')
                    if [[ "$creator_email" == *"@"* ]]; then
                        echo -e "${RED}✗${NC} Creator email should be masked"
                        FAILED_TESTS=$((FAILED_TESTS + 1))
                    else
                        echo -e "${GREEN}✓${NC} Creator email is properly masked"
                    fi
                else
                    echo -e "${RED}✗${NC} Invalid crew object structure"
                    FAILED_TESTS=$((FAILED_TESTS + 1))
                fi
            fi
        else
            echo -e "${RED}✗${NC} Response is not a valid array"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo -e "${RED}✗${NC} Public crews should return 200, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 6))

    # Test CORS headers
    test_cors "/public-crews" "Public crews CORS"
}
