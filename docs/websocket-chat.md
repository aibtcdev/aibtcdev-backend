# WebSocket Chat Documentation

This document provides comprehensive information about the real-time WebSocket chat functionality in aibtcdev-backend.

## Table of Contents

- [Overview](#overview)
- [Connection](#connection)
- [Authentication](#authentication)
- [Message Types](#message-types)
- [Usage Examples](#usage-examples)
- [Session Management](#session-management)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The WebSocket chat API provides real-time bidirectional communication with AI agents. It supports:

- **Real-time messaging**: Instant message delivery and responses
- **Thread-based conversations**: Persistent conversation history
- **Multi-agent support**: Interact with different specialized AI agents
- **Session management**: Automatic connection cleanup and job management
- **Streaming responses**: Live message processing and delivery

## Connection

### Endpoint
```
ws://localhost:8000/chat/ws
wss://your-domain.com/chat/ws
```

### Connection Requirements
- Valid authentication token or API key
- WebSocket-compatible client
- Proper error handling for connection failures

## Authentication

Authentication is required via query parameters:

### Bearer Token
```
ws://localhost:8000/chat/ws?token=your_bearer_token
```

### API Key
```
ws://localhost:8000/chat/ws?key=your_api_key
```

## Message Types

### 1. Chat Message (`message`)

Send a message to an AI agent:

```json
{
  "type": "message",
  "thread_id": "thread-uuid-here",
  "agent_id": "agent-uuid-here",
  "content": "Your message content here"
}
```

**Fields:**
- `type`: Must be `"message"`
- `thread_id`: UUID of the conversation thread
- `agent_id`: UUID of the specific agent (optional)
- `content`: The message text to send

### 2. History Request (`history`)

Request conversation history for a thread:

```json
{
  "type": "history",
  "thread_id": "thread-uuid-here"
}
```

**Fields:**
- `type`: Must be `"history"`
- `thread_id`: UUID of the conversation thread

### 3. Error Response (`error`)

Server-sent error messages:

```json
{
  "type": "error",
  "message": "Error description"
}
```

## Usage Examples

### JavaScript/Browser Example

```javascript
// Establish WebSocket connection
const ws = new WebSocket('ws://localhost:8000/chat/ws?token=your_bearer_token');

// Connection opened
ws.onopen = function(event) {
    console.log('Connected to chat WebSocket');
    
    // Request conversation history
    ws.send(JSON.stringify({
        type: 'history',
        thread_id: 'your-thread-id'
    }));
};

// Receive messages
ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    switch(message.type) {
        case 'message':
            console.log('Received message:', message.content);
            break;
        case 'error':
            console.error('Error:', message.message);
            break;
        default:
            console.log('Unknown message type:', message.type);
    }
};

// Send a chat message
function sendMessage(threadId, content, agentId = null) {
    const message = {
        type: 'message',
        thread_id: threadId,
        content: content
    };
    
    if (agentId) {
        message.agent_id = agentId;
    }
    
    ws.send(JSON.stringify(message));
}

// Handle connection errors
ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};

// Handle connection close
ws.onclose = function(event) {
    console.log('WebSocket connection closed:', event.code, event.reason);
};
```

### Python Example

```python
import asyncio
import json
import websockets

async def chat_client():
    uri = "ws://localhost:8000/chat/ws?token=your_bearer_token"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to chat WebSocket")
        
        # Request history
        history_request = {
            "type": "history",
            "thread_id": "your-thread-id"
        }
        await websocket.send(json.dumps(history_request))
        
        # Send a message
        message = {
            "type": "message",
            "thread_id": "your-thread-id",
            "content": "Hello, AI agent!"
        }
        await websocket.send(json.dumps(message))
        
        # Listen for responses
        async for message in websocket:
            data = json.loads(message)
            
            if data["type"] == "message":
                print(f"Received: {data['content']}")
            elif data["type"] == "error":
                print(f"Error: {data['message']}")

# Run the client
asyncio.run(chat_client())
```

### Node.js Example

```javascript
const WebSocket = require('ws');

const ws = new WebSocket('ws://localhost:8000/chat/ws?token=your_bearer_token');

ws.on('open', function open() {
    console.log('Connected to chat WebSocket');
    
    // Request conversation history
    ws.send(JSON.stringify({
        type: 'history',
        thread_id: 'your-thread-id'
    }));
    
    // Send a message after a delay
    setTimeout(() => {
        ws.send(JSON.stringify({
            type: 'message',
            thread_id: 'your-thread-id',
            content: 'Hello from Node.js!'
        }));
    }, 1000);
});

ws.on('message', function message(data) {
    const message = JSON.parse(data);
    
    switch(message.type) {
        case 'message':
            console.log('AI Response:', message.content);
            break;
        case 'error':
            console.error('Error:', message.message);
            break;
    }
});

ws.on('error', function error(err) {
    console.error('WebSocket error:', err);
});

ws.on('close', function close() {
    console.log('WebSocket connection closed');
});
```

## Session Management

### Automatic Cleanup
- Sessions are automatically cleaned up when connections close
- Running jobs are marked as disconnected but continue processing
- Session IDs are generated for each connection

### Job Processing
- Each message creates a background job for AI processing
- Jobs continue even if the WebSocket disconnects
- Results are saved to the database for later retrieval

### Connection Limits
- Each user can have multiple concurrent connections
- Sessions are isolated by unique session IDs
- Memory usage is managed through automatic cleanup

## Error Handling

### Connection Errors

```javascript
ws.onerror = function(error) {
    console.error('Connection error:', error);
    // Implement reconnection logic
    setTimeout(reconnect, 5000);
};

function reconnect() {
    if (ws.readyState === WebSocket.CLOSED) {
        // Recreate WebSocket connection
        ws = new WebSocket('ws://localhost:8000/chat/ws?token=your_bearer_token');
        setupEventHandlers();
    }
}
```

### Message Validation Errors

Common validation errors:
- Missing required fields (`thread_id`, `content`)
- Invalid UUID format for `thread_id` or `agent_id`
- Unknown message type

### Server Errors

Server-side errors are sent as error messages:
```json
{
  "type": "error",
  "message": "Specific error description"
}
```

## Best Practices

### 1. Connection Management
- Implement automatic reconnection logic
- Handle connection timeouts gracefully
- Monitor connection state before sending messages

### 2. Message Handling
- Validate message format before sending
- Implement proper error handling for all message types
- Use appropriate timeouts for responses

### 3. Thread Management
- Use consistent thread IDs for conversation continuity
- Request history when reconnecting to restore context
- Generate UUIDs properly for new threads

### 4. Performance
- Avoid sending messages too frequently
- Implement client-side message queuing if needed
- Handle large conversation histories efficiently

### 5. Security
- Always use secure WebSocket (WSS) in production
- Implement proper token refresh mechanisms
- Don't log sensitive authentication tokens

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to WebSocket
**Solutions**:
- Verify the server is running and accessible
- Check authentication token validity
- Ensure network connectivity and firewall settings
- Verify WebSocket URL format

**Problem**: Connection drops frequently
**Solutions**:
- Implement reconnection logic with exponential backoff
- Check network stability
- Monitor server logs for connection issues

### Message Issues

**Problem**: Messages not being received
**Solutions**:
- Verify WebSocket connection state
- Check message format and required fields
- Ensure thread_id is valid UUID format
- Monitor server logs for processing errors

**Problem**: Slow response times
**Solutions**:
- Check AI model performance and rate limits
- Monitor server resource usage
- Verify database connectivity
- Consider message complexity and processing requirements

### Authentication Issues

**Problem**: 401 Unauthorized errors
**Solutions**:
- Verify token/API key is valid and not expired
- Check token format in query parameters
- Ensure profile exists for the authenticated user
- Review authentication configuration

### Debug Information

Enable detailed logging by monitoring:
- WebSocket connection events
- Message send/receive timestamps
- Server response times
- Error messages and stack traces

Example debug setup:
```javascript
const ws = new WebSocket('ws://localhost:8000/chat/ws?token=your_token');

// Log all events for debugging
ws.addEventListener('open', (event) => {
    console.log('WebSocket opened:', event);
});

ws.addEventListener('message', (event) => {
    console.log('Message received:', event.data);
});

ws.addEventListener('error', (event) => {
    console.error('WebSocket error:', event);
});

ws.addEventListener('close', (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
});
```
