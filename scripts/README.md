# Scripts Directory

This directory contains utility scripts for the aibtcdev-backend project.

## Available Scripts

### Test Scripts
- **`test_proposal_evaluation.py`** - Test the multi-agent proposal evaluation workflow
- **`test_comprehensive_evaluation.py`** - Test the comprehensive (single-agent) proposal evaluation workflow  
- **`test_xtweet_retrieval.py`** - Test XTweet retrieval from Supabase backend

### Utility Scripts
- **`check_updates.py`** - Check for available updates to dependencies in pyproject.toml
- **`run_task.py`** - CLI tool for running tasks on demand from the job management system

## Usage

All scripts can be run from the project root directory using either `python` or `uv run`:

```bash
# Using python directly
python scripts/test_xtweet_retrieval.py --help

# Using uv run (recommended)
uv run python scripts/test_xtweet_retrieval.py --help
```

### Examples

```bash
# Test XTweet retrieval
uv run python scripts/test_xtweet_retrieval.py --tweet-id "12345678-1234-5678-9012-123456789abc"

# Check for dependency updates
uv run python scripts/check_updates.py

# List available tasks
uv run python scripts/run_task.py list

# Run a specific task
uv run python scripts/run_task.py run agent_account_deployer

# Test proposal evaluation
uv run python scripts/test_proposal_evaluation.py --proposal-id "12345678-1234-5678-9012-123456789abc" --proposal-data "Test proposal content"
```

## Requirements

All scripts automatically handle path resolution to import from the `app` module when run from the project root directory. No additional setup is required beyond having the project dependencies installed. 