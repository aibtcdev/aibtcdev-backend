# Authentication Documentation

This document provides comprehensive information about authentication methods and security practices in aibtcdev-backend.

## Table of Contents

- [Overview](#overview)
- [Authentication Methods](#authentication-methods)
- [Bearer Token Authentication](#bearer-token-authentication)
- [API Key Authentication](#api-key-authentication)
- [WebSocket Authentication](#websocket-authentication)
- [Webhook Authentication](#webhook-authentication)
- [Security Best Practices](#security-best-practices)
- [Token Management](#token-management)
- [Troubleshooting](#troubleshooting)

## Overview

aibtcdev-backend supports multiple authentication methods to provide flexibility for different use cases:

- **Bearer Tokens**: Session-based authentication for web applications
- **API Keys**: Long-lived keys for programmatic access
- **Query Parameters**: Authentication for WebSocket connections
- **Webhook Tokens**: Secure authentication for webhook endpoints

All authenticated requests are associated with a user profile that determines access permissions and agent associations.

## Authentication Methods

### Summary Table

| Method | Use Case | Format | Expiration |
|--------|----------|--------|------------|
| Bearer Token | Web apps, temporary access | `Authorization: Bearer <token>` | Session-based |
| API Key | Programmatic access, bots | `X-API-Key: <key>` | Long-lived |
| Query Params | WebSocket connections | `?token=<token>` or `?key=<key>` | Same as above |
| Webhook Token | Webhook security | `Authorization: Bearer <webhook_token>` | Static |

## Bearer Token Authentication

Bearer tokens are session-based and ideal for web applications where users log in and maintain a session.

### Usage

**HTTP Header Format:**
```
Authorization: Bearer <your_session_token>
```

**Example:**
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     http://localhost:8000/tools/available
```

**JavaScript Example:**
```javascript
const response = await fetch('http://localhost:8000/tools/available', {
  headers: {
    'Authorization': 'Bearer your_session_token'
  }
});
```

**Python Example:**
```python
import requests

headers = {
    'Authorization': 'Bearer your_session_token'
}

response = requests.get('http://localhost:8000/tools/available', headers=headers)
```

### Token Verification Process

1. Token is extracted from the `Authorization` header
2. Token format is validated (must start with "Bearer ")
3. Session token is verified and decoded
4. User identifier (email) is extracted from token
5. Profile is looked up in the database
6. Request proceeds with authenticated profile context

### Token Characteristics

- **Format**: JWT-based session tokens
- **Expiration**: Session-based (varies by implementation)
- **Security**: Includes signature verification
- **Scope**: Full API access for the associated profile

## API Key Authentication

API keys provide long-lived authentication suitable for automated systems, bots, and server-to-server communication.

### Usage

**HTTP Header Format:**
```
X-API-Key: <your_api_key>
```

**Example:**
```bash
curl -H "X-API-Key: 12345678-1234-1234-1234-123456789abc" \
     http://localhost:8000/tools/available
```

**JavaScript Example:**
```javascript
const response = await fetch('http://localhost:8000/tools/available', {
  headers: {
    'X-API-Key': 'your_api_key'
  }
});
```

**Python Example:**
```python
import requests

headers = {
    'X-API-Key': 'your_api_key'
}

response = requests.get('http://localhost:8000/tools/available', headers=headers)
```

### API Key Verification Process

1. API key is extracted from the `X-API-Key` header
2. Key format is validated (must be valid UUID)
3. Key is looked up in the database
4. Key status is verified (must be enabled)
5. Associated profile is retrieved
6. Request proceeds with authenticated profile context

### API Key Characteristics

- **Format**: UUID format (e.g., `12345678-1234-1234-1234-123456789abc`)
- **Expiration**: Long-lived (manually managed)
- **Security**: Database-stored with enable/disable status
- **Scope**: Full API access for the associated profile

## WebSocket Authentication

WebSocket connections require authentication via query parameters since headers cannot be easily set in browser WebSocket APIs.

### Usage

**Token-based:**
```
ws://localhost:8000/chat/ws?token=your_bearer_token
```

**API Key-based:**
```
ws://localhost:8000/chat/ws?key=your_api_key
```

### JavaScript Example

```javascript
// Using Bearer token
const ws1 = new WebSocket('ws://localhost:8000/chat/ws?token=your_bearer_token');

// Using API key
const ws2 = new WebSocket('ws://localhost:8000/chat/ws?key=your_api_key');

ws1.onopen = function(event) {
    console.log('Connected with bearer token');
};

ws2.onopen = function(event) {
    console.log('Connected with API key');
};
```

### Python Example

```python
import asyncio
import websockets

async def connect_with_token():
    uri = "ws://localhost:8000/chat/ws?token=your_bearer_token"
    async with websockets.connect(uri) as websocket:
        print("Connected with bearer token")

async def connect_with_key():
    uri = "ws://localhost:8000/chat/ws?key=your_api_key"
    async with websockets.connect(uri) as websocket:
        print("Connected with API key")
```

### Authentication Process

1. Authentication parameters are extracted from query string
2. Priority order: API key (`key`) is checked first, then bearer token (`token`)
3. Same verification process as HTTP requests
4. Profile context is established for the WebSocket session
5. Connection proceeds with authenticated context

## Webhook Authentication

Webhooks use a dedicated authentication token to ensure only authorized systems can trigger webhook endpoints.

### Configuration

Set the webhook authentication token in your environment:
```bash
AIBTC_WEBHOOK_AUTH_TOKEN="Bearer your_webhook_secret_token"
```

### Usage

**HTTP Header Format:**
```
Authorization: Bearer <webhook_token>
```

**Example:**
```bash
curl -X POST -H "Authorization: Bearer your_webhook_secret_token" \
     -H "Content-Type: application/json" \
     -d '{"event": "dao_created"}' \
     http://localhost:8000/webhooks/dao
```

### Webhook Endpoints

- `POST /webhooks/chainhook` - Blockchain event processing
- `POST /webhooks/dao` - DAO creation events

### Security Features

- **Static Token**: Uses a pre-configured secret token
- **Bearer Format**: Follows standard Authorization header format
- **Environment Variable**: Token stored securely in environment
- **Exact Match**: Token must match exactly (no partial matches)

## Security Best Practices

### Token Storage

**DO:**
- Store tokens in environment variables
- Use secure storage mechanisms (keychains, vaults)
- Implement token rotation where possible
- Log token usage for security monitoring

**DON'T:**
- Hard-code tokens in source code
- Store tokens in plain text files
- Share tokens via insecure channels
- Log token values in application logs

### Network Security

**Use HTTPS/WSS in Production:**
```javascript
// Production
const ws = new WebSocket('wss://api.yourdomain.com/chat/ws?token=...');

// Development only
const ws = new WebSocket('ws://localhost:8000/chat/ws?token=...');
```

**Implement Proper CORS:**
- Configure allowed origins appropriately
- Don't use wildcards (*) in production
- Validate origin headers

### Error Handling

**Avoid Exposing Sensitive Information:**
```javascript
// Good - Generic error handling
try {
  const response = await apiCall();
} catch (error) {
  console.error('Authentication failed');
  // Don't log the actual token
}

// Bad - Exposing token details
catch (error) {
  console.error('Failed with token:', token); // Never do this
}
```

## Token Management

### Obtaining Tokens

1. **Bearer Tokens**: Obtained through the authentication flow (login process)
2. **API Keys**: Generated through the admin interface or API
3. **Webhook Tokens**: Configured by system administrators

### Token Lifecycle

**Bearer Tokens:**
- Created during user authentication
- Expire after session timeout
- Automatically refreshed (implementation dependent)
- Revoked on logout

**API Keys:**
- Created manually through admin interface
- No automatic expiration
- Can be enabled/disabled
- Manually revoked when needed

### Token Validation

All tokens are validated for:
- Proper format and structure
- Existence in the system
- Active status (not disabled/revoked)
- Associated profile existence
- Permission levels

## Troubleshooting

### Common Authentication Errors

#### 401 Unauthorized

**Possible Causes:**
- Invalid or expired token
- Missing authentication header
- Incorrect header format
- Disabled API key
- Non-existent profile

**Solutions:**
```bash
# Check token format
curl -v -H "Authorization: Bearer your_token" http://localhost:8000/tools/available

# Verify API key format (should be UUID)
curl -v -H "X-API-Key: 12345678-1234-1234-1234-123456789abc" http://localhost:8000/tools/available

# Check WebSocket authentication
# Browser DevTools -> Network -> WS -> Check connection response
```

#### 404 Profile Not Found

**Possible Causes:**
- Valid token but no associated profile
- Profile was deleted
- Database connectivity issues

**Solutions:**
- Verify profile exists in database
- Check profile association with token/key
- Ensure database is accessible

#### WebSocket Connection Failures

**Possible Causes:**
- Incorrect query parameter format
- Network connectivity issues
- Invalid token in query string

**Debug Steps:**
```javascript
const ws = new WebSocket('ws://localhost:8000/chat/ws?token=your_token');

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
    // Check browser network tab for detailed error
};

ws.onclose = function(event) {
    console.log('Close code:', event.code);
    console.log('Close reason:', event.reason);
    // 1006 = abnormal closure (often auth issues)
    // 1002 = protocol error
    // 1003 = unsupported data
};
```

### Testing Authentication

**Test Bearer Token:**
```bash
# Should return 200 with tools list
curl -H "Authorization: Bearer valid_token" http://localhost:8000/tools/available

# Should return 401
curl -H "Authorization: Bearer invalid_token" http://localhost:8000/tools/available

# Should return 401 (missing Bearer prefix)
curl -H "Authorization: invalid_format" http://localhost:8000/tools/available
```

**Test API Key:**
```bash
# Should return 200 with tools list
curl -H "X-API-Key: valid_uuid_key" http://localhost:8000/tools/available

# Should return 401
curl -H "X-API-Key: invalid_key" http://localhost:8000/tools/available
```

**Test WebSocket:**
```javascript
// Test valid authentication
const ws1 = new WebSocket('ws://localhost:8000/chat/ws?token=valid_token');

// Test invalid authentication (should fail to connect)
const ws2 = new WebSocket('ws://localhost:8000/chat/ws?token=invalid_token');

// Monitor connection states
[ws1, ws2].forEach((ws, index) => {
    ws.onopen = () => console.log(`WS${index + 1}: Connected`);
    ws.onerror = (error) => console.error(`WS${index + 1}: Error`, error);
    ws.onclose = (event) => console.log(`WS${index + 1}: Closed`, event.code);
});
```

### Debugging Tips

1. **Enable Verbose Logging**: Use `-v` flag with curl to see headers
2. **Check Browser DevTools**: Network tab shows WebSocket connection details
3. **Monitor Server Logs**: Authentication errors are logged server-side
4. **Validate Token Format**: Ensure tokens match expected format
5. **Test with Known Good Tokens**: Use working tokens to isolate issues