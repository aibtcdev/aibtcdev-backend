# Agent Account Deployer - Automatic Funding

The Agent Account Deployer task has been enhanced to automatically queue STX funding for newly deployed agent accounts. This ensures that deployed agent accounts have initial STX available for operations.

## Overview

After successfully deploying an agent account contract, the deployer automatically:

1. **Creates STX Transfer Message**: Queues a message for the STX Transfer Task
2. **Funds Agent Contract**: Sends initial STX to the deployed contract address
3. **Tracks Results**: Reports funding status in deployment results

## Configuration

The funding behavior is controlled by these constants in the `AgentAccountDeployerTask` class:

```python
DEFAULT_AGENT_FUNDING_AMOUNT = 1    # STX to send to newly deployed agent accounts
DEFAULT_AGENT_FUNDING_FEE = 400     # microSTX transaction fee
```

## Funding Process

### When Funding Occurs

Automatic funding is triggered after:
- ✅ **Successful new deployment**: When a new agent account contract is deployed
- ✅ **Existing contract found**: When `ContractAlreadyExists` error occurs (contract was already deployed)

### Funding Details

Each funded agent account receives:
- **Amount**: 1 STX (configurable via `DEFAULT_AGENT_FUNDING_AMOUNT`)
- **Fee**: 200 microSTX (configurable via `DEFAULT_AGENT_FUNDING_FEE`)
- **Recipient**: The deployed contract principal (e.g., `SP1ABC...DEF.aibtc-acct-12345`)
- **Memo**: Descriptive text: `"Initial funding for deployed agent account: {contract_principal}"`

### Funding Source

The funding automatically uses the backend wallet (same as used for deployment):

```python
# Uses backend wallet automatically (wallet_id=None)
funding_success = self._create_agent_funding_message(
    contract_principal=full_contract_principal,
    dao_id=str(message.dao_id) if message.dao_id else None
)
```

When `wallet_id` is `None`, the STX Transfer Task automatically uses the backend wallet configured in `config.backend_wallet.seed_phrase` - the same wallet used for agent account deployment.

## Queue Message Format

The automatically created STX transfer message follows this format:

```python
QueueMessageCreate(
    type=QueueMessageType.get_or_create("stx_transfer"),
    wallet_id=None,       # None = use backend wallet for funding
    dao_id=dao_id,        # Optional: Associated DAO
    message={
        "recipient": "SP1ABC...DEF.aibtc-acct-12345",  # Agent contract address
        "amount": 1,                                    # STX amount
        "fee": 400,                                    # microSTX fee
        "memo": "Initial funding for deployed agent account: SP1ABC...DEF.aibtc-acct-12345"
    }
)
```

## Result Tracking

The deployment results now include funding information:

```python
@dataclass
class AgentAccountDeployResult(RunnerResult):
    accounts_processed: int = 0
    accounts_deployed: int = 0
    funding_messages_created: int = 0    # New: Tracks funding messages
    errors: List[str] = None
```

### Individual Message Results

Each deployment message result includes:

```python
{
    "success": True,
    "deployed": True,
    "result": { /* deployment details */ },
    "funding_queued": True    # New: Whether funding was queued
}
```

## Logging

The enhanced logging provides detailed funding information:

```
INFO: Agent account deployed with contract: SP1ABC...DEF.aibtc-acct-12345
INFO: Updated agent 123e4567-e89b-12d3-a456-426614174000 with contract address: SP1ABC...DEF.aibtc-acct-12345
INFO: Created STX funding message abc123de-f456-789a-bcde-f0123456789a to send 1 STX to agent contract SP1ABC...DEF.aibtc-acct-12345
INFO: Queued initial funding for agent contract: SP1ABC...DEF.aibtc-acct-12345
```

## Error Handling

Funding failures are handled gracefully:

- **Non-Critical**: Funding failures don't stop the deployment process
- **Logged**: Failed funding attempts are logged as warnings
- **Tracked**: Results indicate whether funding was successfully queued
- **Recoverable**: Failed funding can be manually retried

Example error handling:
```
WARNING: Failed to queue funding for agent contract: SP1ABC...DEF.aibtc-acct-12345
```

## Integration with STX Transfer Task

The funding messages are processed by the [STX Transfer Task](stx-transfer-task.md):

1. **Automatic Processing**: STX Transfer Task picks up funding messages
2. **High Priority**: Funding transfers are processed with high priority
3. **Retry Logic**: Failed transfers are automatically retried
4. **Monitoring**: Full monitoring and error tracking for funding transfers

## Manual Funding

If automatic funding fails, you can manually create funding messages:

```python
from app.backend.factory import backend
from app.backend.models import QueueMessageCreate, QueueMessageType

# Manual funding using backend wallet (same as automatic funding)
message = QueueMessageCreate(
    type=QueueMessageType.get_or_create("stx_transfer"),
    wallet_id=None,  # Use backend wallet
    message={
        "recipient": "SP1ABC...DEF.aibtc-acct-12345",  # Agent contract address
        "amount": 1,
        "memo": "Manual funding for agent account"
    }
)

created_message = backend.create_queue_message(message)
```

Or using a specific wallet:

```python
from examples.stx_transfer_example import create_stx_transfer_message

# Manual funding from specific wallet
message_id = create_stx_transfer_message(
    wallet_id=specific_wallet_id,
    recipient="SP1ABC...DEF.aibtc-acct-12345",
    amount=1,
    memo="Manual funding for agent account"
)
```

## Future Enhancements

### Configurable Funding

Consider making funding amounts configurable per DAO or agent type:

```python
# Per-DAO funding configuration
funding_config = get_dao_funding_config(dao_id)
funding_amount = funding_config.agent_funding_amount or DEFAULT_AGENT_FUNDING_AMOUNT
```

### Conditional Funding

Add logic to check if funding is needed before creating transfer messages:

```python
# Check if agent contract already has sufficient balance
contract_balance = get_contract_balance(contract_principal)
if contract_balance < minimum_required_balance:
    create_funding_message(...)
```

## Monitoring and Alerts

Monitor funding operations through:

- **Deployment Results**: Check `funding_messages_created` in task results
- **STX Transfer Task**: Monitor funding transfer success rates
- **Wallet Balances**: Track treasury wallet balance for funding capacity
- **Failed Funding**: Alert on persistent funding failures

## Security Considerations

- **Wallet Security**: Ensure funding wallet private keys are secure
- **Amount Limits**: Configure reasonable funding amounts to prevent abuse
- **Rate Limiting**: Monitor funding frequency to detect anomalies
- **Access Control**: Restrict who can modify funding configuration
