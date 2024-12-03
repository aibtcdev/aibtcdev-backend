#!/bin/bash

# Source utils
source "$(dirname "$0")/utils.sh"

test_metrics() {
    echo "Testing metrics endpoints..."

    # Test crews_metrics endpoint
    response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/crews_metrics")
    body=$(echo "$response" | head -n1)
    status=$(echo "$response" | tail -n1)

    if [ "$status" -eq 200 ]; then
        # Validate JSON structure
        if echo "$body" | jq -e '.total_crews | type == "number"' >/dev/null && \
           echo "$body" | jq -e '.crews_by_date | type == "object"' >/dev/null; then
            echo -e "${GREEN}✓${NC} Crews metrics returns valid response structure"
        else
            echo -e "${RED}✗${NC} Invalid crews metrics response structure"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo -e "${RED}✗${NC} Crews metrics should return 200, got $status"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Validate date format in crews_by_date
    if echo "$body" | jq -e 'select(.crews_by_date != null) | .crews_by_date | keys[] | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$")' >/dev/null; then
        echo -e "${GREEN}✓${NC} Crews metrics dates are in correct format (YYYY-MM-DD)"
    else
        echo -e "${RED}✗${NC} Invalid date format in crews_by_date"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Validate crews array in crews_by_date
    if echo "$body" | jq -e '.crews_by_date | values[] | arrays' >/dev/null; then
        echo -e "${GREEN}✓${NC} Crews metrics contains valid arrays of crew names"
    else
        echo -e "${RED}✗${NC} Invalid crews array structure in crews_by_date"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Test CORS headers
    test_cors "/crews_metrics" "Crews metrics CORS"
}
