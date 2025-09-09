# handlers Folder Documentation

## Overview
This folder contains specialized event handlers for processing Chainhook webhook events in a blockchain context. It defines base classes and specific handlers for events like proposals, votes, conclusions, airdrops, and lottery calculations, using abstract base classes (ABC) and dataclass patterns for structured event handling. Key technologies include Python dataclasses and abstract methods for extensible event processing.

## Key Components
- **Files**:
  - action_concluder_handler.py: Handles action conclusion events.
  - action_proposal_handler.py: Processes action proposal submissions.
  - action_veto_handler.py: Manages veto actions on proposals.
  - action_vote_handler.py: Handles voting events on actions.
  - airdrop_ft_handler.py: Processes fungible token airdrop events.
  - airdrop_stx_handler.py: Handles STX airdrop events.
  - base_proposal_handler.py: Base class for proposal-related handlers.
  - base.py: Defines the base ChainhookEventHandler ABC with methods for transaction and block handling.
  - base_vote_handler.py: Base class for vote-related handlers.
  - block_state_handler.py: Manages block state updates.
  - buy_event_handler.py: Processes buy events.
  - core_proposal_handler.py: Handles core proposal events.
  - core_vote_handler.py: Manages core voting events.
  - dao_proposal_burn_height_handler.py: Processes DAO proposal burn height events.
  - dao_proposal_conclusion_handler.py: Handles DAO proposal conclusions.
  - dao_proposal_handler.py: Manages DAO proposal submissions.
  - dao_vote_handler.py: Processes DAO voting events.
  - __init__.py: Initialization file for the package.
  - lottery_utils.py: Utilities for quorum calculations and lottery selections, including QuorumCalculator and LotterySelection classes.
  - sell_event_handler.py: Handles sell events.

- **Subfolders**:
  - (None)

## Relationships and Integration
Handlers in this folder extend the base ChainhookEventHandler and are instantiated or referenced in the parent folder's handler.py or service.py for webhook processing. They interact with models from app/services/integrations/webhooks/chainhook/models.py for data parsing and may queue messages using app/backend/models.py for further processing in job tasks.

## Navigation
- **Parent Folder**: [Up: chainhook Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Handlers are designed for extensibility; new event types can be added by subclassing the base handler. Ensure blockchain event data is validated before processing to avoid errors.
