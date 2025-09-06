# STX Transfer Task

The STX Transfer Task processes queue messages to send STX tokens to recipients using the `WalletSendSTX` tool. This task is designed for automated STX transfers through the job management system.

## Overview

The STX Transfer Task (`stx_transfer`) is a high-priority task that:
- Processes queue messages containing STX transfer requests
- Validates transfer parameters (recipient, amount, wallet ID)
- Executes transfers using the `WalletSendSTX` tool
- Provides comprehensive error handling and retry logic
- Supports batch processing for multiple transfers

## Configuration

The task is configured with the following parameters:

```python
@job(
    job_type="stx_transfer",
    name="STX Transfer Processor",
    description="Processes STX transfer requests from queue",
    interval_seconds=30,          # Check for new messages every 30 seconds
    priority=JobPriority.HIGH,    # High priority processing
    max_retries=3,               # Retry failed transfers up to 3 times
    retry_delay_seconds=60,      # Wait 60 seconds between retries
    timeout_seconds=180,         # 3-minute timeout per transfer
    max_concurrent=1,            # Process one batch at a time
    requires_blockchain=True,    # Requires blockchain connectivity
    batch_size=5,               # Process up to 5 transfers per batch
    enable_dead_letter_queue=True,
)
```

## Queue Message Format

To trigger an STX transfer, create a queue message with the following structure:

```python
from app.backend.models import QueueMessageCreate, QueueMessageType

queue_message = QueueMessageCreate(
    type=QueueMessageType.get_or_create("stx_transfer"),
    wallet_id=wallet_uuid,  # Required: UUID of the sending wallet
    dao_id=dao_uuid,        # Optional: Associated DAO ID
    message={
        "recipient": "SP1ABC123...",  # Required: STX recipient address
        "amount": 5,                  # Required: Amount in STX (not microSTX)
        "fee": 400,                  # Optional: Fee in microSTX (default: 200)
        "memo": "Payment for..."     # Optional: Transaction memo
    }
)
```

### Required Fields

- **`wallet_id`**: UUID of the wallet to send STX from (or `null` to use backend wallet)
- **`message.recipient`**: Valid STX address (starts with SP or ST)
- **`message.amount`**: Positive integer amount in STX

### Optional Fields

- **`dao_id`**: UUID of associated DAO (for tracking purposes)
- **`message.fee`**: Transaction fee in microSTX (default: 200)
- **`message.memo`**: Text memo for the transaction (default: empty)

## Backend Wallet Usage

When `wallet_id` is set to `null`, the STX Transfer Task automatically uses the backend wallet configured in `config.backend_wallet.seed_phrase`. This is particularly useful for:

- **Agent Account Funding**: Automatic funding of newly deployed agent accounts
- **Treasury Operations**: Centralized funding from a treasury wallet
- **System Transactions**: Automated transfers that don't belong to specific users

The backend wallet mode provides the same functionality as regular wallet transfers but uses the seed phrase directly instead of a wallet ID.

## Usage Examples

### Single Transfer

```python
from uuid import UUID
from app.backend.factory import backend
from app.backend.models import QueueMessageCreate, QueueMessageType

# Create a single STX transfer using a user wallet
message = QueueMessageCreate(
    type=QueueMessageType.get_or_create("stx_transfer"),
    wallet_id=UUID("12345678-1234-1234-1234-123456789abc"),
    message={
        "recipient": "SP1ABC123DEF456GHI789JKL012MNO345PQR678",
        "amount": 10,
        "fee": 250,
        "memo": "Payment for services"
    }
)

created_message = backend.create_queue_message(message)
print(f"Created transfer message: {created_message.id}")
```

### Backend Wallet Transfer

```python
# Create a transfer using the backend wallet (wallet_id=None)
message = QueueMessageCreate(
    type=QueueMessageType.get_or_create("stx_transfer"),
    wallet_id=None,  # Use backend wallet
    message={
        "recipient": "SP1ABC123DEF456GHI789JKL012MNO345PQR678",
        "amount": 1,
        "fee": 400,
        "memo": "Initial funding for agent account"
    }
)

created_message = backend.create_queue_message(message)
print(f"Created backend wallet transfer message: {created_message.id}")
```

### Batch Transfers

```python
# Create multiple transfers
transfers = [
    {
        "wallet_id": UUID("wallet-1"),
        "recipient": "SP1ABC...",
        "amount": 5,
        "memo": "Payment 1"
    },
    {
        "wallet_id": UUID("wallet-2"),
        "recipient": "SP2DEF...",
        "amount": 3,
        "memo": "Payment 2"
    }
]

for transfer in transfers:
    message = QueueMessageCreate(
        type=QueueMessageType.get_or_create("stx_transfer"),
        wallet_id=transfer["wallet_id"],
        message={
            "recipient": transfer["recipient"],
            "amount": transfer["amount"],
            "memo": transfer["memo"]
        }
    )
    backend.create_queue_message(message)
```

### Using the Helper Functions

See `examples/stx_transfer_example.py` for helper functions:

```python
from examples.stx_transfer_example import create_stx_transfer_message

# Simple transfer
message_id = create_stx_transfer_message(
    wallet_id=UUID("12345678-1234-1234-1234-123456789abc"),
    recipient="SP1ABC123DEF456GHI789JKL012MNO345PQR678",
    amount=5,
    memo="Test payment"
)
```

## Task Processing

The task processes transfers in the following stages:

1. **Validation**: Checks message format and required fields
2. **Tool Initialization**: Creates `WalletSendSTX` tool with wallet ID
3. **Transfer Execution**: Calls the tool to send STX
4. **Result Processing**: Updates queue message with results
5. **Error Handling**: Logs errors and marks failed transfers

## Error Handling

The task includes comprehensive error handling:

### Retryable Errors
- Network connectivity issues
- Blockchain RPC timeouts
- Temporary service unavailability

### Non-Retryable Errors
- Invalid message format
- Missing required fields
- Insufficient wallet funds
- Invalid recipient addresses

### Error Messages

Failed transfers are marked with detailed error information:

```json
{
    "success": false,
    "error": "Insufficient funds for transfer",
    "result": { /* detailed error from WalletSendSTX tool */ }
}
```

## Monitoring

The task provides detailed metrics:

```python
@dataclass
class STXTransferResult(RunnerResult):
    transfers_processed: int = 0     # Total messages processed
    transfers_successful: int = 0    # Successful transfers
    total_amount_sent: int = 0      # Total STX sent
    errors: List[str] = None        # List of error messages
```

## Security Considerations

- **Wallet Access**: Ensure wallet IDs are valid and accessible
- **Amount Limits**: Consider implementing transfer limits for safety
- **Address Validation**: Recipients must be valid STX addresses
- **Fee Management**: Monitor transaction fees to avoid overpayment

## Integration

The STX Transfer Task integrates with:

- **Job Management System**: Automatic scheduling and retry logic
- **Wallet Tools**: Uses `WalletSendSTX` for actual transfers
- **Queue System**: Processes messages from the queue table
- **Logging**: Comprehensive logging for monitoring and debugging

## Running the Task

The task runs automatically when the job management system is active. To manually trigger or test:

```bash
# Run specific task (if supported by your setup)
python -m app.services.infrastructure.job_management.tasks.stx_transfer_task

# Or use the job runner system
python scripts/run_task.py stx_transfer
```

## Troubleshooting

### Common Issues

1. **"Wallet ID is required"**: Ensure `wallet_id` is set in the queue message
2. **"Invalid message data"**: Check that `recipient` and `amount` are provided
3. **"Insufficient funds"**: Verify wallet has enough STX for transfer + fees
4. **"Network error"**: Check blockchain connectivity and RPC endpoints

### Debugging

Enable debug logging to see detailed transfer information:

```python
import logging
logging.getLogger("app.services.infrastructure.job_management.tasks.stx_transfer_task").setLevel(logging.DEBUG)
```

This will log:
- Message validation details
- Transfer parameters
- Tool execution results
- Error details
