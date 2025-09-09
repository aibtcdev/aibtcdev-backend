# tools Folder Documentation

## Overview
This folder implements various tools for agent accounts, blockchain interactions, database, and social integrations. It uses script runners and tool classes for executable logic.

## Key Components
- **Files**:
  - agent_account_action_proposals.py: Action proposal tools.
  - agent_account_asset_management.py: Asset deposit tools.
  - agent_account_configuration.py: Configuration tools.
  - agent_account_faktory.py: Faktory tools.
  - agent_account.py: Core agent account tools.
  - bitflow.py: Bitflow integrations.
  - bun.py: Bun script runner.
  - contracts.py: Contract utilities.
  - dao_base_dao.py: Base DAO tools.
  - dao_deployments.py: DAO deployment tools.
  - dao_ext_action_proposals.py: Extended proposal tools.
  - dao_ext_charter.py: Charter tools.
  - dao_ext_treasury.py: Treasury tools.
  - database.py: Database tools.
  - faktory.py: Faktory client.
  - __init__.py: Initialization file for the package.
  - hiro.py: Hiro tools.
  - lunarcrush.py: LunarCrush tools.
  - telegram.py: Telegram tools.
  - tools_factory.py: Factory for tool initialization.
  - transactions.py: Transaction utilities.
  - twitter.py: Twitter tools.
  - wallet.py: Wallet tools.
  - x_credentials.py: X credentials tools.

- **Subfolders**:
  - (None)

## Relationships and Integration
Tools are exposed via API in app/api/tools/ and used in job tasks (app/services/infrastructure/job_management/tasks/). Factory integrates with services.

## Navigation
- **Parent Folder**: [Up: app Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Tools are modular; add new ones via the factory.
