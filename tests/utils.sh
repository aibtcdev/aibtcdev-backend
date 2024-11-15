#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Shared test addresses
TEST_ADDRESSES=(
    "SP3GEF4KYM4V41FHC9NX0F7K0GW1VC6A4WNJ855X3"
    "SP2733BAJCTWBM0790KC9GZYMP73S0VDYPRSAF95"
    "SP2CZP2W4PCD22GWXFYYKV40JXZBWVFN692T0FJQH"
    "SP22JJ7N9RN6ZDY2F6M2DHSDTYN4P768AHF3AG90A"
    "SPK0PEGF4Z37H0D6V1JEMGTD7BE36MHT75P8548J"
)

# tests an endpoint against several criteria
test_endpoint() {
    local endpoint=$1
    local expected_status=$2
    local description=$3
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    # Make the request and capture headers and body using -i
    response=$(curl -s -i -w "\n%{http_code}" -X GET "${API_URL}${endpoint}")
    
    # Parse response (modified to handle -i output)
    status=$(echo "$response" | tail -n1)
    headers=$(echo "$response" | grep -i "^[a-z-]*:" || true)
    body=$(echo "$response" | awk 'BEGIN{RS="\r\n\r\n"} NR==2')
    
    local test_failed=false

    # Check status code
    if [ "$status" -eq "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} $description - Status: $status"
    else
        echo -e "${RED}✗${NC} $description - Expected status $expected_status, got $status"
        test_failed=true
    fi
    
    # Check CORS headers (case-insensitive)
    if ! echo "$headers" | grep -qi "access-control-allow-origin:"; then
        echo -e "${RED}✗${NC} Missing CORS headers for $endpoint"
        test_failed=true
    fi
    
    # Check content type (case-insensitive)
    if ! echo "$headers" | grep -qi "content-type:.*application/json"; then
        echo -e "${RED}✗${NC} Missing or incorrect Content-Type header for $endpoint"
        test_failed=true
    fi
    
    # Validate JSON response
    if ! echo "$body" | jq . >/dev/null 2>&1; then
        echo -e "${RED}✗${NC} Invalid JSON response for $endpoint"
        test_failed=true
    fi

    # Only increment failure counter once per endpoint
    if [ "$test_failed" = true ]; then
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# Test OPTIONS request for CORS
test_cors() {
    local endpoint=$1
    local description=$2
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    response=$(curl -s -w "\n%{http_code}" -X OPTIONS \
        -H "Origin: http://localhost:3000" \
        -H "Access-Control-Request-Method: GET" \
        "${API_URL}${endpoint}")
    
    status=$(echo "$response" | tail -n1)
    
    if [ "$status" -eq 200 ]; then
        echo -e "${GREEN}✓${NC} $description - CORS preflight OK"
    else
        echo -e "${RED}✗${NC} $description - CORS preflight failed"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}
