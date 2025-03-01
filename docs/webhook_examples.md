# Webhook API Examples

This document provides examples of how to call the webhook endpoints with proper authentication.

## Authentication

All webhook endpoints require Bearer token authentication. You need to include an `Authorization` header with a valid token:

```
Authorization: Bearer your-webhook-auth-token
```

The token must match the one configured in the `AIBTC_WEBHOOK_AUTH_TOKEN` environment variable.

## Chainhook Webhook

### Example Request

```bash
curl -X POST https://your-api-url/webhooks/chainhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-webhook-auth-token" \
  -d '{
    "apply": [
      {
        "block_identifier": {
          "index": 12345,
          "hash": "0x1234567890abcdef"
        },
        "transactions": [
          {
            "transaction_identifier": {
              "hash": "0xabcdef1234567890"
            },
            "operations": [
              {
                "type": "contract_call",
                "contract_identifier": "SP123...",
                "contract_call": {
                  "function_name": "example-function",
                  "function_args": []
                }
              }
            ]
          }
        ]
      }
    ]
  }'
```

### Example Response

```json
{
  "success": true,
  "message": "Webhook processed successfully",
  "data": {
    "processed_transactions": 1
  }
}
```

## DAO Creation Webhook

### Example Request

```bash
curl -X POST https://your-api-url/webhooks/dao \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-webhook-auth-token" \
  -d '{
    "dao": {
      "name": "Example DAO",
      "description": "This is an example DAO",
      "contract_address": "SP123..."
    },
    "extensions": [
      {
        "type": "voting",
        "contract_address": "SP456..."
      }
    ],
    "token": {
      "name": "Example Token",
      "symbol": "EXT",
      "contract_address": "SP789..."
    }
  }'
```

### Example Response

```json
{
  "success": true,
  "message": "DAO created successfully",
  "data": {
    "dao_id": "123e4567-e89b-12d3-a456-426614174000",
    "extensions": [
      {
        "id": "234e5678-e89b-12d3-a456-426614174001",
        "type": "voting"
      }
    ],
    "token_id": "345e6789-e89b-12d3-a456-426614174002"
  }
}
```

## Error Responses

### Authentication Failure

```json
{
  "detail": "Missing Authorization header"
}
```

```json
{
  "detail": "Invalid Authorization format. Use 'Bearer <token>'"
}
```

```json
{
  "detail": "Invalid authentication token"
}
```

### Processing Failure

```json
{
  "detail": "Error processing webhook"
}
```

```json
{
  "detail": "Error processing DAO creation webhook: [specific error message]"
}
``` 