# migrations Folder Documentation

## Overview
This folder contains database migration scripts for Supabase, managing schema changes like table additions and column renames. It uses SQL files for versioned database updates.

## Key Components
- **Files**:
  - 20250101000000_rename_proposal_tx_id_to_proposal_id.sql: Renames proposal fields.
  - 20250729013749_remote_schema.sql: Adds remote schema.
  - 20250729013909_add_veto_table.sql: Adds veto table.
  - 20250809163631_add_airdrops_table.sql: Adds airdrops table.
  - 20250810000000_add_airdrop_id_to_proposals.sql: Adds airdrop ID to proposals.
  - 20250817000000_add_chainhook_uuid_to_chain_states.sql: Adds Chainhook UUID.
  - 20250823000000_add_feedback_table.sql: Adds feedback table.
  - 20250825000000_add_lottery_results_table.sql: Adds lottery results table.

- **Subfolders**:
  - (None)

## Relationships and Integration
Migrations are applied via Supabase tools and align with models in app/backend/models.py. Used during deployment setups documented in docs/supabase-deployments.md.

## Navigation
- **Parent Folder**: [Up: supabase Folder README](../README.md)
- **Child Folders** (if applicable): 
  - (None)

## Additional Notes
Migrations are timestamped; run in order to maintain database integrity.
