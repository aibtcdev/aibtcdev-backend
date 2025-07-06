# API Overview

This document provides a comprehensive overview of all available API endpoints in aibtcdev-backend.

## Table of Contents

- [Authentication](#authentication)
- [Chat API](#chat-api)
- [Tools API](#tools-api)
- [Webhooks API](#webhooks-api)
- [Response Formats](#response-formats)
- [Error Handling](#error-handling)

## Authentication

All API endpoints require authentication using one of the following methods:

- **Bearer Token**: `Authorization: Bearer <token>`
- **API Key**: `X-API-Key: <api_key>`
- **Query Parameters**: `?token=<token>` or `?key=<api_key>` (for WebSocket)

## Chat API

Base path: `/chat`

### WebSocket Chat
- **Endpoint**: `WS /chat/ws`
- **Authentication**: Query parameter (`?token=<token>` or `?key=<api_key>`)
- **Description**: Real-time bidirectional chat with AI agents
- **Message Types**:
  - `message`: Send chat messages
  - `history`: Request conversation history

## Tools API

Base path: `/tools`

### Tool Discovery

#### Get Available Tools
- **Endpoint**: `GET /tools/available`
- **Query Parameters**:
  - `category` (optional): Filter tools by category
- **Description**: Returns a list of all available tools with their descriptions

#### Get Tool Categories
- **Endpoint**: `GET /tools/categories`
- **Description**: Returns a list of all available tool categories

#### Search Tools
- **Endpoint**: `GET /tools/search`
- **Query Parameters**:
  - `query` (required): Search query for tool name or description
  - `category` (optional): Filter by category
- **Description**: Search for tools by name or description

### Trading & Finance

#### Execute Faktory Buy Order
- **Endpoint**: `POST /tools/faktory/execute_buy`
- **Body Parameters**:
  - `btc_amount` (string): Amount of BTC to spend
  - `dao_token_dex_contract_address` (string): Contract principal where the DAO token is listed
  - `slippage` (string, optional): Slippage tolerance in basis points (default: "15")
- **Description**: Execute a buy order on Faktory DEX

#### Fund Wallet with Testnet STX
- **Endpoint**: `POST /tools/wallet/fund_testnet_faucet`
- **Description**: Request testnet STX tokens from the faucet

#### Fund with Testnet sBTC
- **Endpoint**: `POST /tools/faktory/fund_testnet_sbtc`
- **Description**: Request testnet sBTC tokens from Faktory faucet

### DAO Management

#### Create DAO Action Proposal
- **Endpoint**: `POST /tools/dao/action_proposals/propose_send_message`
- **Body Parameters**:
  - `agent_account_contract` (string): Contract principal of the agent account
  - `action_proposals_voting_extension` (string): Contract principal for DAO action proposals
  - `action_proposal_contract_to_execute` (string): Contract principal of the action proposal
  - `dao_token_contract_address` (string): Contract principal of the DAO token
  - `message` (string): Message to be sent through the DAO proposal system
  - `memo` (string, optional): Optional memo for the proposal
- **Description**: Create a proposal for sending a message via the DAO action proposal system

#### Veto DAO Action Proposal
- **Endpoint**: `POST /tools/dao/action_proposals/veto_proposal`
- **Body Parameters**:
  - `dao_action_proposal_voting_contract` (string): Contract principal for DAO action proposals
  - `proposal_id` (string): ID of the proposal to veto
- **Description**: Veto an existing DAO action proposal

#### Generate Proposal Recommendation
- **Endpoint**: `POST /tools/dao/proposal_recommendations/generate`
- **Body Parameters**:
  - `dao_id` (UUID): The ID of the DAO
  - `focus_area` (string, optional): Specific area of focus (default: "general improvement")
  - `specific_needs` (string, optional): Specific needs or requirements
  - `model_name` (string, optional): LLM model to use (default: "gpt-4.1")
  - `temperature` (number, optional): Temperature for LLM generation (default: 0.1)
- **Description**: Generate AI-powered proposal recommendations for a DAO

### Agent Account Management

#### Approve Contract for Agent Account
- **Endpoint**: `POST /tools/agent_account/approve_contract`
- **Body Parameters**:
  - `agent_account_contract` (string): Contract principal of the agent account
  - `contract_to_approve` (string): The contract principal to approve
- **Description**: Approve a contract for use with an agent account

### AI Evaluation

#### Run Comprehensive Evaluation
- **Endpoint**: `POST /tools/evaluation/comprehensive`
- **Body Parameters**:
  - `proposal_id` (string): Unique identifier for the proposal
  - `proposal_content` (string, optional): Override proposal content
  - `dao_id` (UUID, optional): DAO ID for context
  - `custom_system_prompt` (string, optional): Custom system prompt
  - `custom_user_prompt` (string, optional): Custom user prompt
  - `config` (object, optional): Configuration for the evaluation agent
- **Description**: Run comprehensive AI evaluation on a proposal

#### Get Default Evaluation Prompts
- **Endpoint**: `GET /tools/evaluation/default_prompts`
- **Description**: Get the default system and user prompts for comprehensive evaluation

### Social Media Integration

#### Get Twitter Embed Data
- **Endpoint**: `GET /tools/twitter/oembed`
- **Query Parameters**:
  - `url` (required): Twitter/X.com URL to embed
  - `media_max_width` (optional): Maximum width for media (default: 560)
  - `hide_thread` (optional): Whether to hide the thread (default: false)
- **Description**: Proxy endpoint for Twitter oembed API to avoid CORS issues

## Webhooks API

Base path: `/webhooks`

### Blockchain Event Processing

#### Chainhook Webhook
- **Endpoint**: `POST /webhooks/chainhook`
- **Authentication**: Bearer token via `Authorization` header
- **Description**: Process blockchain events from chainhook services

#### DAO Creation Webhook
- **Endpoint**: `POST /webhooks/dao`
- **Authentication**: Bearer token via `Authorization` header
- **Description**: Handle DAO creation events and setup associated entities

## Response Formats

### Success Response
```json
{
  "success": true,
  "output": "Operation completed successfully",
  "data": { ... }
}
```

### Error Response
```json
{
  "type": "error",
  "message": "Description of the error"
}
```

### WebSocket Message Format
```json
{
  "type": "message|history|error",
  "thread_id": "uuid",
  "content": "message content",
  "agent_id": "uuid (optional)"
}
```

## Error Handling

### HTTP Status Codes
- `200`: Success
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (invalid or missing authentication)
- `404`: Not Found (resource doesn't exist)
- `408`: Request Timeout
- `500`: Internal Server Error

### Common Error Types
- **Authentication Errors**: Invalid or expired tokens
- **Validation Errors**: Missing or invalid request parameters
- **Resource Errors**: Requested resource not found
- **Network Errors**: Blockchain or external service connectivity issues
- **Rate Limit Errors**: API rate limits exceeded

### WebSocket Error Handling
WebSocket connections automatically handle disconnections and provide error messages in the following format:
```json
{
  "type": "error",
  "message": "Error description"
}
```
