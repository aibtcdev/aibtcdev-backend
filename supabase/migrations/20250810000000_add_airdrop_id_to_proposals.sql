-- Add airdrop_id foreign key column to proposals table
-- This allows linking proposals to specific airdrop records

-- Add airdrop_id column to proposals table
alter table public.proposals 
add column if not exists airdrop_id uuid;

-- Add foreign key constraint to airdrops table
alter table public.proposals 
add constraint fk_proposals_airdrop_id 
foreign key (airdrop_id) 
references public.airdrops(id) 
on delete set null;

-- Create index for query performance
create index if not exists idx_proposals_airdrop_id 
on public.proposals(airdrop_id);

-- Add comment for documentation
comment on column public.proposals.airdrop_id is 'Foreign key reference to airdrops table for linked airdrop data';
