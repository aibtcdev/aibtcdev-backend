# Task CLI Usage Guide

The `run_task.py` CLI script provides a command-line interface to interact with the job management system, allowing you to list available tasks, run specific tasks, and monitor their execution.

## Prerequisites

Make sure you have the environment set up and dependencies installed:

```bash
# Install dependencies
pip install -r requirements.txt

# Or if using uv (recommended)
uv sync
```

## Basic Usage

The CLI script supports several commands:

### 1. List Available Tasks

```bash
# List all tasks in table format
python run_task.py list



# List tasks in JSON format
python run_task.py list --format json

# List only enabled tasks
python run_task.py list --enabled-only

# Filter by priority level
python run_task.py list --priority high
```

### 2. Run a Specific Task

```bash
# Run a task with default settings
python run_task.py run agent_account_deployer

# Run with custom timeout
python run_task.py run chain_state_monitor --timeout 600

# Run with verbose output
python run_task.py run dao_deployment --verbose

# Run with parameters (JSON format)
python run_task.py run dao_proposal_vote --parameters '{"proposal_id": "123", "vote": "yes"}'
```

### 3. Show Task Information

```bash
# Show detailed information about a specific task
python run_task.py info agent_account_deployer
python run_task.py info dao_token_holders_monitor
```

### 4. Show System Status

```bash
# Show system status in table format
python run_task.py status

# Show system status in JSON format
python run_task.py status --format json
```

### 5. Show Task Metrics

```bash
# Show metrics for all tasks
python run_task.py metrics

# Show metrics for a specific task
python run_task.py metrics agent_account_deployer

# Show metrics in JSON format
python run_task.py metrics --format json
```

## Available Tasks

Here are the currently available tasks in the system:

- **agent_account_deployer**: Deploys agent account contracts
- **chain_state_monitor**: Monitors blockchain state for synchronization
- **dao_deployment**: Processes DAO deployment requests
- **dao_deployment_tweet**: Generates congratulatory tweets for deployed DAOs
- **dao_proposal_conclude**: Processes and concludes DAO proposals
- **dao_proposal_embedder**: Generates embeddings for DAO proposals
- **dao_proposal_evaluation**: Evaluates DAO proposals using AI
- **dao_proposal_vote**: Processes and votes on DAO proposals
- **dao_token_holders_monitor**: Monitors and syncs DAO token holders
- **discord**: Sends Discord messages from queue
- **tweet**: Processes and sends tweets for DAOs

## Examples

### Example 1: Check what tasks are available
```bash
python run_task.py list --enabled-only
```

### Example 2: Run the chain state monitor
```bash
python run_task.py run chain_state_monitor --verbose
```

### Example 3: Check detailed info about a task
```bash
python run_task.py info dao_deployment
```

### Example 4: Monitor system health
```bash
python run_task.py status
```

### Example 5: Check task performance metrics
```bash
python run_task.py metrics agent_account_deployer
```

## Task Parameters

Some tasks may accept parameters. Use the `--parameters` flag with JSON format:

```bash
# Example with parameters
python run_task.py run custom_task --parameters '{"param1": "value1", "param2": 123}'
```

## Output Formats

Most commands support both table and JSON output formats:

- **Table format**: Human-readable, formatted output (default)
- **JSON format**: Machine-readable output for scripting

Use `--format json` to get JSON output for any command that supports it.

## Error Handling

The CLI tool includes comprehensive error handling:

- **Timeout errors**: Tasks that run too long will be terminated
- **Parameter errors**: Invalid JSON parameters will be caught and reported
- **Task not found**: Clear error message when trying to run non-existent tasks
- **Validation errors**: Tasks that fail validation will report the specific issue

## Tips

1. **Always check task info first**: Use `info` command to understand what a task does before running it
2. **Use verbose mode for debugging**: Add `--verbose` flag to see detailed execution information
3. **Monitor system status**: Use `status` command to check overall system health
4. **Check metrics regularly**: Use `metrics` command to monitor task performance
5. **Filter tasks by priority**: Use `--priority` flag to focus on specific task types

## Development Usage

For development and testing:

```bash
# Run a task with extended timeout for debugging
python run_task.py run dao_deployment --timeout 900 --verbose

# Check system status after running tasks
python run_task.py status --format json | jq '.health_status'

# Monitor specific task metrics
python run_task.py metrics chain_state_monitor --format json
```

This CLI tool integrates with the existing job management system and provides a convenient way to manually trigger tasks, monitor their execution, and debug issues during development. 