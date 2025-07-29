-- Create vetos table for tracking DAO proposal vetos
create table if not exists public.vetos (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now() not null,
  updated_at timestamptz default now() not null,
  
  -- Core identifiers
  wallet_id uuid references public.wallets(id),
  dao_id uuid references public.daos(id),
  agent_id uuid references public.agents(id),
  proposal_id uuid references public.proposals(id),
  profile_id uuid references public.profiles(id),
  
  -- Transaction details
  tx_id text,
  address text,
  amount text, -- String to handle large token amounts
  contract_caller text,
  tx_sender text,
  
  -- Veto metadata
  vetoer_user_id integer,
  reasoning text
);

-- Add indexes for common queries
create index if not exists idx_vetos_proposal_id on public.vetos(proposal_id);
create index if not exists idx_vetos_dao_id on public.vetos(dao_id);
create index if not exists idx_vetos_agent_id on public.vetos(agent_id);
create index if not exists idx_vetos_wallet_id on public.vetos(wallet_id);
create index if not exists idx_vetos_tx_id on public.vetos(tx_id);
create index if not exists idx_vetos_address on public.vetos(address);
create index if not exists idx_vetos_created_at on public.vetos(created_at);

-- Add updated_at trigger
create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger handle_vetos_updated_at
  before update on public.vetos
  for each row
  execute function public.handle_updated_at();

-- Add row level security (RLS)
alter table public.vetos enable row level security;

-- Create policy for authenticated users to read vetos
create policy "Users can view vetos" on public.vetos
  for select using (auth.role() = 'authenticated');

-- Create policy for users to insert vetos for their own profiles
create policy "Users can insert vetos for their profiles" on public.vetos
  for insert with check (
    auth.uid() = profile_id or
    auth.uid() in (
      select profiles.id from profiles 
      where profiles.id = profile_id
    )
  );

-- Add comments for documentation
comment on table public.vetos is 'Tracks veto votes on DAO action proposals';
comment on column public.vetos.wallet_id is 'Reference to the wallet that cast the veto';
comment on column public.vetos.dao_id is 'Reference to the DAO where the veto was cast';
comment on column public.vetos.agent_id is 'Reference to the agent that cast the veto';
comment on column public.vetos.proposal_id is 'Reference to the proposal being vetoed';
comment on column public.vetos.tx_id is 'Blockchain transaction ID for the veto';
comment on column public.vetos.address is 'Blockchain address of the vetoer';
comment on column public.vetos.amount is 'Token amount used for the veto (as string for large numbers)';
comment on column public.vetos.contract_caller is 'Smart contract that initiated the veto';
comment on column public.vetos.tx_sender is 'Transaction sender address';
comment on column public.vetos.vetoer_user_id is 'User ID of the person who cast the veto';
comment on column public.vetos.reasoning is 'Optional text explaining the reason for the veto';
