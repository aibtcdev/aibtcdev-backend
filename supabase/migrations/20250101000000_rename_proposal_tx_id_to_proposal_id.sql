-- Rename proposal_tx_id column to proposal_id in airdrops table
-- This aligns with the updated data model where airdrops link to proposals via UUID rather than transaction ID

-- Drop the existing index
drop index if exists public.idx_airdrops_proposal_tx_id;

-- Rename the column from proposal_tx_id to proposal_id
alter table public.airdrops rename column proposal_tx_id to proposal_id;

-- Update the column type to UUID to match proposals table
alter table public.airdrops alter column proposal_id type uuid using proposal_id::uuid;

-- Create new index on the renamed column
create index if not exists idx_airdrops_proposal_id on public.airdrops(proposal_id);

-- Update the comment to reflect the new purpose
comment on column public.airdrops.proposal_id is 'UUID reference to proposals table if this airdrop was used to boost a proposal (NULL if not used)';

-- Add foreign key constraint to proposals table (optional, uncomment if desired)
-- alter table public.airdrops 
--   add constraint fk_airdrops_proposal_id 
--   foreign key (proposal_id) references public.proposals(id) 
--   on delete set null;
