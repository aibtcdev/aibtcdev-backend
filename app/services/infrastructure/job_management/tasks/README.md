# tasks Folder Documentation

## Overview
This folder defines specific job tasks for background processing, such as DAO deployments, monitoring, and message handling. Tasks are decorated with @job for auto-discovery, using dataclass configs and async methods for execution, with priorities, retries, and monitoring.

## Key Components
- **Files**:
  - [agent_account_deployer.py](agent_account_deployer.py): Deploys agent accounts.
  - [agent_account_proposal_approval_task.py](agent_account_proposal_approval_task.py): Approves agent proposals.
  - [agent_wallet_balance_monitor.py](agent_wallet_balance_monitor.py): Monitors wallet balances.
  - [chainhook_monitor.py](chainhook_monitor.py): Monitors Chainhook events.
  - [chain_state_monitor.py](chain_state_monitor.py): Monitors chain states.
  - [dao_deployment_task.py](dao_deployment_task.py): Processes DAO deployments.
  - [dao_deployment_tweet_task.py](dao_deployment_tweet_task.py): Generates tweets for deployments.
  - [dao_proposal_concluder.py](dao_proposal_concluder.py): Concludes DAO proposals.
  - [dao_proposal_embedder.py](dao_proposal_embedder.py): Embeds proposals for search.
  - [dao_proposal_evaluation.py](dao_proposal_evaluation.py): Evaluates proposals.
  - [dao_proposal_voter.py](dao_proposal_voter.py): Handles proposal voting.
  - [dao_token_holders_monitor.py](dao_token_holders_monitor.py): Monitors token holders.
  - [discord_task.py](discord_task.py): Sends Discord messages.
  - [__init__.py](__init__.py): Initialization file for the package.
  - [stx_transfer_task.py](stx_transfer_task.py): Processes STX transfers.
  - [tweet_task.py](tweet_task.py): Processes and sends tweets.

- **Subfolders**:
  - (None)

## Relationships and Integration
Tasks extend BaseTask from the parent folder's base.py and are registered via auto_discovery.py and decorators.py. They interact with backend services (app/backend/supabase.py) for data access and may queue messages using app/backend/models.py.

## Navigation
- **Parent Folder**: [Up: job_management Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Tasks support dynamic registration; add new ones with the @job decorator. Configure retries and priorities based on task criticality.
# tasks Folder Documentation

## Overview
This folder contains job task implementations for the infrastructure system, including DAO operations, agent management, blockchain monitoring, and message processing. Tasks use decorators for scheduling and extend BaseTask for common functionality. Key technologies include async methods, dataclasses for results, and integration with backend models.

## Key Components
- **Files**:
  - agent_account_deployer.py: Deploys agent account contracts using backend wallet.
  - agent_account_proposal_approval_task.py: Approves DAO contracts for agent voting.
  - agent_wallet_balance_monitor.py: Monitors and auto-funds low-balance agent wallets.
  - chainhook_monitor.py: Monitors and recreates failed chainhooks.
  - chain_state_monitor.py: Syncs blockchain state using chainhook adapter.
  - dao_deployment_task.py: Processes DAO deployment requests via AI tools.
  - dao_deployment_tweet_task.py: Generates congratulatory tweets for deployed DAOs.
  - dao_proposal_concluder.py: Concludes DAO proposals using backend tools.
  - dao_proposal_embedder.py: Generates embeddings for new DAO proposals.
  - dao_proposal_evaluation.py: Evaluates proposals using AI workflows.
  - dao_proposal_voter.py: Processes and casts votes on DAO proposals.
  - dao_token_holders_monitor.py: Syncs DAO token holders with blockchain data.
  - discord_task.py: Sends Discord messages from queue using webhooks.
  - __init__.py: Initialization file for the package.
  - stx_transfer_task.py: Processes STX transfer requests from queue.
  - tweet_task.py: Sends tweets from queue using Twitter service.

- **Subfolders**:
  - (None)

## Relationships and Integration
Tasks extend BaseTask from app/services/infrastructure/job_management/base.py and are auto-registered via decorators. They interact with backend models from app/backend/models.py and services like HiroApi for blockchain data.

## Navigation
- **Parent Folder**: [Up: job_management Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Tasks are discovered automatically; add new ones by creating files with @job decorators. Monitor queue messages for processing status.
