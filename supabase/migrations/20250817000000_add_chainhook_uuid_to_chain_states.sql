-- Migration: Add chainhook_uuid field to chain_states table
-- Description: Adds a nullable chainhook_uuid field to track associated chainhook IDs for monitoring
-- Created: 2025-01-17

-- Add chainhook_uuid column to chain_states table
ALTER TABLE chain_states 
ADD COLUMN chainhook_uuid TEXT NULL;

-- Add comment to document the purpose of the new column
COMMENT ON COLUMN chain_states.chainhook_uuid IS 'UUID of the chainhook associated with this chain state for monitoring purposes';

-- Create an index on chainhook_uuid for efficient lookups
CREATE INDEX IF NOT EXISTS idx_chain_states_chainhook_uuid 
ON chain_states (chainhook_uuid);

-- Create an index on network and chainhook_uuid combination for efficient filtering
CREATE INDEX IF NOT EXISTS idx_chain_states_network_chainhook_uuid 
ON chain_states (network, chainhook_uuid);