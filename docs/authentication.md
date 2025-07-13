# Authentication Documentation

This document provides comprehensive information about authentication methods and security practices in aibtcdev-backend.

## Table of Contents

- [Overview](#overview)
- [Authentication Methods](#authentication-methods)
- [Bearer Token Authentication](#bearer-token-authentication)
- [API Key Authentication](#api-key-authentication)
- [Webhook Authentication](#webhook-authentication)
- [Security Best Practices](#security-best-practices)
- [Token Management](#token-management)
- [Troubleshooting](#troubleshooting)

## Overview

aibtcdev-backend supports multiple authentication methods to provide flexibility for different use cases:

- **Bearer Tokens**: Session-based authentication for web applications
- **API Keys**: Long-lived keys for programmatic access
- **Webhook Tokens**: Secure authentication for webhook endpoints

All authenticated requests are associated with a user profile that determines access permissions and agent associations.

## Authentication Methods

### Summary Table

| Method | Use Case | Format | Expiration |
|--------|----------|--------|------------|
| Bearer Token | Web apps, temporary access | `Authorization: Bearer <token>` | Session-based |
| API Key | Programmatic access, bots | `X-API-Key: <key>` | Long-lived |
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
     http://localhost:8000/tools/
```

**JavaScript Example:**
```javascript
const response = await fetch('http://localhost:8000/tools/', {
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

response = requests.get('http://localhost:8000/tools/', headers=headers)
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
     http://localhost:8000/tools/
```

**JavaScript Example:**
```javascript
const response = await fetch('http://localhost:8000/tools/', {
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

response = requests.get('http://localhost:8000/tools/', headers=headers)
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

**Use HTTPS in Production:**
```javascript
// Production - Always use HTTPS
const response = await fetch('https://api.yourdomain.com/tools/', {
  headers: {
    'Authorization': 'Bearer your_token'
  }
});

// Development only - HTTP acceptable
const response = await fetch('http://localhost:8000/tools/', {
  headers: {
    'Authorization': 'Bearer your_token'
  }
});
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
curl -v -H "Authorization: Bearer your_token" http://localhost:8000/tools/

# Verify API key format (should be UUID)
curl -v -H "X-API-Key: 12345678-1234-1234-1234-123456789abc" http://localhost:8000/tools/
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

### Testing Authentication

**Test Bearer Token:**
```bash
# Should return 200 with tools list
curl -H "Authorization: Bearer valid_token" http://localhost:8000/tools/

# Should return 401
curl -H "Authorization: Bearer invalid_token" http://localhost:8000/tools/

# Should return 401 (missing Bearer prefix)
curl -H "Authorization: invalid_format" http://localhost:8000/tools/
```

**Test API Key:**
```bash
# Should return 200 with tools list
curl -H "X-API-Key: valid_uuid_key" http://localhost:8000/tools/

# Should return 401
curl -H "X-API-Key: invalid_key" http://localhost:8000/tools/
```

### Debugging Tips

1. **Enable Verbose Logging**: Use `-v` flag with curl to see headers
2. **Check Browser DevTools**: Network tab shows request details
3. **Monitor Server Logs**: Authentication errors are logged server-side
4. **Validate Token Format**: Ensure tokens match expected format
5. **Test with Known Good Tokens**: Use working tokens to isolate issues

### Authentication Flow Testing

**JavaScript/TypeScript Testing:**
```javascript
// Test different authentication methods
const testAuthentication = async () => {
  // Test Bearer token
  try {
    const response = await fetch('http://localhost:8000/tools/', {
      headers: { 'Authorization': 'Bearer test_token' }
    });
    console.log('Bearer token status:', response.status);
  } catch (error) {
    console.error('Bearer token failed:', error);
  }

  // Test API key
  try {
    const response = await fetch('http://localhost:8000/tools/', {
      headers: { 'X-API-Key': 'test_api_key' }
    });
    console.log('API key status:', response.status);
  } catch (error) {
    console.error('API key failed:', error);
  }
};
```

**Python Testing:**
```python
import requests

def test_authentication():
    base_url = 'http://localhost:8000/tools/'
    
    # Test Bearer token
    try:
        response = requests.get(base_url, headers={
            'Authorization': 'Bearer test_token'
        })
        print(f'Bearer token status: {response.status_code}')
    except Exception as e:
        print(f'Bearer token failed: {e}')
    
    # Test API key
    try:
        response = requests.get(base_url, headers={
            'X-API-Key': 'test_api_key'
        })
        print(f'API key status: {response.status_code}')
    except Exception as e:
        print(f'API key failed: {e}')

test_authentication()
```