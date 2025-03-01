# Chat API Reference

This document provides a technical reference for the WebSocket-based Chat API.

## API Endpoint

```
WebSocket: /chat/ws
```

## Authentication

Authentication is required for all WebSocket connections. Provide one of the following query parameters:

| Parameter | Type   | Description                                |
|-----------|--------|--------------------------------------------|
| `token`   | string | Bearer token for authentication            |
| `key`     | string | API key for authentication                 |

## Message Format

All messages sent to and received from the WebSocket are JSON objects. Each message must include a `type` field that indicates the message type.

### Client Message Types

#### History Request

Request message history for a specific thread.

```json
{
  "type": "history",
  "thread_id": "string (UUID)"
}
```

| Field      | Type   | Required | Description                      |
|------------|--------|----------|----------------------------------|
| `type`     | string | Yes      | Must be "history"                |
| `thread_id`| string | Yes      | UUID of the thread               |

#### Chat Message

Send a new message to a thread.

```json
{
  "type": "message",
  "thread_id": "string (UUID)",
  "agent_id": "string (UUID) or null",
  "content": "string"
}
```

| Field      | Type   | Required | Description                      |
|------------|--------|----------|----------------------------------|
| `type`     | string | Yes      | Must be "message"                |
| `thread_id`| string | Yes      | UUID of the thread               |
| `agent_id` | string | No       | UUID of the agent to use, or null for default |
| `content`  | string | Yes      | The message content              |

### Server Message Types

#### Message

A message in the conversation.

```json
{
  "type": "message",
  "id": "string",
  "thread_id": "string (UUID)",
  "role": "string",
  "content": "string",
  "created_at": "string (ISO 8601 datetime)"
}
```

| Field       | Type   | Description                                |
|-------------|--------|--------------------------------------------|
| `type`      | string | "message"                                  |
| `id`        | string | Unique identifier for the message          |
| `thread_id` | string | UUID of the thread                         |
| `role`      | string | Either "user" or "assistant"               |
| `content`   | string | The message content                        |
| `created_at`| string | ISO 8601 formatted datetime                |

#### Message Received

Acknowledgment that a message was received and is being processed.

```json
{
  "type": "message_received",
  "id": "string",
  "thread_id": "string (UUID)",
  "job_id": "string"
}
```

| Field       | Type   | Description                                |
|-------------|--------|--------------------------------------------|
| `type`      | string | "message_received"                         |
| `id`        | string | Unique identifier for the message          |
| `thread_id` | string | UUID of the thread                         |
| `job_id`    | string | Identifier for the processing job          |

#### Error

An error message.

```json
{
  "type": "error",
  "message": "string"
}
```

| Field     | Type   | Description                                |
|-----------|--------|--------------------------------------------|
| `type`    | string | "error"                                    |
| `message` | string | Description of the error                   |

## Error Codes

The WebSocket connection may return standard WebSocket close codes:

| Code | Description                 | Handling Strategy                        |
|------|-----------------------------|------------------------------------------|
| 1000 | Normal closure              | Normal operation                         |
| 1001 | Going away                  | Reconnect if needed                      |
| 1002 | Protocol error              | Check message format                     |
| 1003 | Unsupported data            | Check message format                     |
| 1008 | Policy violation            | Check authentication                     |
| 1011 | Internal server error       | Retry with exponential backoff           |

Additionally, HTTP status codes may be returned before the WebSocket connection is established:

| Code | Description                 | Handling Strategy                        |
|------|-----------------------------|------------------------------------------|
| 401  | Unauthorized                | Check authentication credentials         |
| 404  | Not found                   | Check endpoint URL                       |
| 500  | Internal server error       | Retry with exponential backoff           |

## Rate Limiting

The Chat API implements rate limiting to prevent abuse. Clients should respect the following limits:

- Maximum of 10 messages per minute per user
- Maximum of 100 messages per hour per user

When rate limits are exceeded, the server will close the WebSocket connection with code 1008 (Policy Violation).

## Thread Lifecycle

Threads are the primary organizational unit for conversations. Each thread has the following lifecycle:

1. **Creation**: A thread is implicitly created when the first message is sent with a new thread ID
2. **Active**: Messages can be sent to and received from the thread
3. **Archived**: After 30 days of inactivity, threads are archived but still accessible
4. **Deleted**: Threads may be deleted according to data retention policies

## Implementation Notes

### Connection Management

- Clients should implement reconnection logic with exponential backoff
- Connections may be terminated after 5 minutes of inactivity
- A single client should maintain only one WebSocket connection at a time

### Message Processing

- Messages within a thread are processed in the order they are received
- Large messages may be rejected (maximum content size: 4KB)
- Binary messages are not supported

### Security Considerations

- Authentication tokens should be kept secure
- All communication is encrypted via TLS
- Do not send sensitive information in message content

## API Versioning

The current API version is v1. Future versions may be introduced with breaking changes.

To ensure compatibility, clients should:

1. Handle unknown message types gracefully
2. Ignore unknown fields in messages
3. Check for API announcements regarding deprecation and new features 