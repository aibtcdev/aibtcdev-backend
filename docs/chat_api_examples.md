# Chat API Examples

This document provides examples of how to use the WebSocket-based Chat API.

## Authentication

The Chat API requires authentication using either a Bearer token or an API key. These can be provided as query parameters:

- `token`: Bearer token for authentication
- `key`: API key for authentication

## WebSocket Connection

### Establishing a Connection

To establish a WebSocket connection, connect to the `/chat/ws` endpoint with your authentication credentials:

```javascript
// Using a Bearer token
const socket = new WebSocket('wss://your-api-url/chat/ws?token=your-bearer-token');

// Or using an API key
const socket = new WebSocket('wss://your-api-url/chat/ws?key=your-api-key');
```

### Message Types

The Chat API supports two main message types:

1. **History Messages**: Request message history for a thread
2. **Chat Messages**: Send a new message to a thread

All messages are JSON objects with a `type` field indicating the message type.

## Requesting Message History

To request the message history for a thread, send a message with the following format:

```javascript
const historyRequest = {
  type: 'history',
  thread_id: '123e4567-e89b-12d3-a456-426614174000'
};

socket.send(JSON.stringify(historyRequest));
```

### Example Response

The server will respond with a series of messages representing the thread history:

```javascript
// Message from user
{
  "type": "message",
  "id": "msg_123",
  "thread_id": "123e4567-e89b-12d3-a456-426614174000",
  "role": "user",
  "content": "Hello, can you help me with something?",
  "created_at": "2023-06-15T14:30:00Z"
}

// Message from assistant
{
  "type": "message",
  "id": "msg_124",
  "thread_id": "123e4567-e89b-12d3-a456-426614174000",
  "role": "assistant",
  "content": "Of course! I'd be happy to help. What do you need assistance with?",
  "created_at": "2023-06-15T14:30:15Z"
}
```

## Sending a Chat Message

To send a new message to a thread, use the following format:

```javascript
const chatMessage = {
  type: 'message',
  thread_id: '123e4567-e89b-12d3-a456-426614174000',
  agent_id: '234e5678-e89b-12d3-a456-426614174001', // Optional, can be null
  content: 'I need help understanding how DAOs work.'
};

socket.send(JSON.stringify(chatMessage));
```

### Example Response

The server will process your message and respond with one or more messages:

```javascript
// Acknowledgment of received message
{
  "type": "message_received",
  "id": "msg_125",
  "thread_id": "123e4567-e89b-12d3-a456-426614174000",
  "job_id": "job_123"
}

// Assistant's response (may come in multiple parts for streaming)
{
  "type": "message",
  "id": "msg_126",
  "thread_id": "123e4567-e89b-12d3-a456-426614174000",
  "role": "assistant",
  "content": "A DAO, or Decentralized Autonomous Organization, is a blockchain-based organization...",
  "created_at": "2023-06-15T14:35:00Z"
}
```

## Error Handling

If an error occurs, the server will send an error message:

```javascript
{
  "type": "error",
  "message": "Thread ID is required"
}
```

Common error scenarios include:
- Missing or invalid authentication
- Invalid thread ID
- Unknown message type
- Server processing errors

## Complete Example

Here's a complete example using JavaScript:

```javascript
// Connect to the WebSocket
const socket = new WebSocket('wss://your-api-url/chat/ws?token=your-bearer-token');

// Handle connection open
socket.onopen = function(e) {
  console.log('Connection established');
  
  // Request thread history
  const historyRequest = {
    type: 'history',
    thread_id: '123e4567-e89b-12d3-a456-426614174000'
  };
  socket.send(JSON.stringify(historyRequest));
};

// Handle messages from server
socket.onmessage = function(event) {
  const message = JSON.parse(event.data);
  
  if (message.type === 'error') {
    console.error('Error:', message.message);
    return;
  }
  
  console.log('Received message:', message);
  
  // Display message in UI
  if (message.type === 'message') {
    displayMessage(message);
  }
};

// Handle errors
socket.onerror = function(error) {
  console.error('WebSocket Error:', error);
};

// Handle connection close
socket.onclose = function(event) {
  if (event.wasClean) {
    console.log(`Connection closed cleanly, code=${event.code}, reason=${event.reason}`);
  } else {
    console.error('Connection died');
  }
};

// Function to send a new message
function sendMessage(content) {
  const chatMessage = {
    type: 'message',
    thread_id: '123e4567-e89b-12d3-a456-426614174000',
    agent_id: null,
    content: content
  };
  socket.send(JSON.stringify(chatMessage));
}

// Example UI function to display messages
function displayMessage(message) {
  const messageElement = document.createElement('div');
  messageElement.className = `message ${message.role}`;
  messageElement.textContent = message.content;
  document.getElementById('chat-container').appendChild(messageElement);
}
```

## Python Example

Here's an example using Python with the `websockets` library:

```python
import asyncio
import json
import websockets
import uuid

async def chat_client():
    # Connect to the WebSocket with authentication
    uri = "wss://your-api-url/chat/ws?token=your-bearer-token"
    
    async with websockets.connect(uri) as websocket:
        # Generate a new thread ID or use an existing one
        thread_id = str(uuid.uuid4())
        
        # Request thread history (if using an existing thread)
        history_request = {
            "type": "history",
            "thread_id": thread_id
        }
        await websocket.send(json.dumps(history_request))
        
        # Process history messages
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data}")
            
            # After receiving history, send a new message
            if data.get("type") == "message":
                # Send a new message
                chat_message = {
                    "type": "message",
                    "thread_id": thread_id,
                    "agent_id": None,
                    "content": "Hello, I'd like to learn about blockchain technology."
                }
                await websocket.send(json.dumps(chat_message))
                break  # Break after sending one message for this example
        
        # Continue processing responses
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data}")

# Run the client
asyncio.run(chat_client())
```

## Notes and Best Practices

1. **Thread Management**:
   - Create a new thread ID (UUID) for each new conversation
   - Reuse the same thread ID to continue an existing conversation

2. **Error Handling**:
   - Always implement proper error handling for WebSocket connections
   - Handle reconnection logic for network interruptions

3. **Message Processing**:
   - Process messages based on their `type` field
   - For streaming responses, accumulate content until complete

4. **Authentication**:
   - Keep authentication tokens secure
   - Implement token refresh logic if tokens expire

5. **Performance**:
   - Limit the frequency of message requests to avoid rate limiting
   - Consider implementing backoff strategies for reconnection attempts 