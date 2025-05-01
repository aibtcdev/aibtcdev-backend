# Chainhook Parsing Service

## Overview

The Chainhook parsing service is a specialized component within the backend that processes and handles blockchain-related webhook events. It's designed to parse, validate, and process webhook payloads from the Chainhook service, which monitors blockchain events and state changes.

## Architecture

The service is composed of three main components:

1. **ChainhookService** (`service.py`)
   - Acts as the main entry point for webhook processing
   - Coordinates between the parser and handler components
   - Implements the base WebhookService interface

2. **ChainhookParser** (`parser.py`)
   - Responsible for parsing raw webhook payloads into structured data
   - Implements comprehensive validation and type checking
   - Converts JSON data into strongly-typed Python objects

3. **ChainhookHandler** (`handler.py`)
   - Manages the processing of parsed webhook events
   - Coordinates multiple specialized handlers for different event types
   - Implements a sequential processing pipeline

## Data Models

The service uses a comprehensive set of data models (`models.py`) to represent blockchain data:

- `ChainHookData`: Top-level container for webhook payloads
- `ChainHookInfo`: Metadata about the webhook configuration
- `Apply`: Represents block-level data and transactions
- `BlockIdentifier`: Block hash and index information
- `TransactionWithReceipt`: Detailed transaction data with receipts
- `Operation`: Individual blockchain operations
- `Event`: Transaction events and their data
- `Receipt`: Transaction receipts and execution results

## Event Handlers

The service includes several specialized handlers for different types of blockchain events:

- `BlockStateHandler`: Processes block-level state changes
- `BuyEventHandler`: Handles purchase-related events
- `SellEventHandler`: Processes sale-related events
- `DAOProposalHandler`: Manages DAO proposal events
- `DAOVoteHandler`: Handles DAO voting events
- `ContractMessageHandler`: Processes smart contract messages
- `DAOProposalBurnHeightHandler`: Handles proposal burn height events
- `DAOProposalConclusionHandler`: Processes proposal conclusions

## Processing Pipeline

The webhook processing follows a sequential pipeline:

1. **Parsing Phase**
   - Raw JSON payload is received
   - Data is validated and converted to typed objects
   - Structured data is created using the defined models

2. **Handling Phase**
   - Block-level processing occurs first
   - Transaction-level processing follows
   - Each handler processes events it's responsible for
   - Post-processing cleanup is performed

3. **Error Handling**
   - Comprehensive error catching and logging
   - Structured error responses
   - Transaction rollback support

## Usage

The service is automatically initialized when webhook events are received. It processes events in the following order:

1. The webhook payload is received by the service
2. The parser converts the raw data into structured objects
3. The handler coordinates processing through specialized handlers
4. Results are logged and any necessary actions are taken

## Logging

The service implements comprehensive logging using the project's standard logging configuration:

- DEBUG level for detailed processing information
- INFO level for standard operation logging
- ERROR level for exception handling
- Contextual information included in all log messages

## Error Handling

The service implements robust error handling:

- Specific exception types for different error scenarios
- Comprehensive error logging
- Transaction rollback support
- Structured error responses

## Security Considerations

- Input validation on all webhook payloads
- Type checking and sanitization
- Secure handling of sensitive blockchain data
- Proper error handling to prevent information leakage

## Dependencies

The service relies on several key components:

- Base webhook service infrastructure
- Logging configuration
- Type hints from the Python typing library
- JSON parsing and validation
- Blockchain-specific data models

## Future Considerations

- Potential for parallel processing of transactions
- Enhanced monitoring and metrics
- Additional specialized handlers for new event types
- Performance optimizations for large block processing 