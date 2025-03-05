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

The DAO webhook is used to record a new DAO in the system (not for deployment).

### Example Request

```bash
curl -X POST https://your-api-url/webhooks/dao \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-webhook-auth-token" \
  -d '{
    "name": "Example DAO",
    "mission": "To build a better future with blockchain",
    "description": "This is an example DAO for demonstration purposes",
    "extensions": [
      {
        "type": "voting",
        "contract_principal": "SP123...",
        "tx_id": "0xabcdef1234567890"
      },
      {
        "type": "treasury",
        "contract_principal": "SP456...",
        "tx_id": "0x0987654321fedcba"
      }
    ],
    "token": {
      "name": "Example Token",
      "symbol": "EXT",
      "decimals": 6,
      "max_supply": "1000000000",
      "contract_principal": "SP789...",
      "tx_id": "0x1122334455667788",
      "description": "Governance token for Example DAO",
      "uri": "https://example.com/token",
      "image_url": "https://example.com/token.png",
      "x_url": "https://x.com/exampletoken",
      "telegram_url": "https://t.me/exampletoken",
      "website_url": "https://example.com"
    }
  }'
```

### Example Response

```json
{
  "success": true,
  "message": "Successfully created DAO 'Example DAO' with ID: 123e4567-e89b-12d3-a456-426614174000",
  "data": {
    "dao_id": "123e4567-e89b-12d3-a456-426614174000",
    "extension_ids": [
      "234e5678-e89b-12d3-a456-426614174001",
      "345e6789-e89b-12d3-a456-426614174002"
    ],
    "token_id": "456e7890-e89b-12d3-a456-426614174003"
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