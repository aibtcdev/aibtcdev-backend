-- Create airdrops table for tracking airdrop transactions
create table if not exists public.airdrops (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now() not null,
  updated_at timestamptz default now() not null,
  
  -- Unique transaction identifier
  tx_hash text unique not null,
  
  -- Blockchain metadata
  block_height integer not null,
  timestamp timestamptz not null,
  sender text not null,
  contract_identifier text not null,
  token_identifier text not null,
  success boolean not null,
  
  -- Airdrop details
  total_amount_airdropped text not null, -- String to handle large numbers
  recipients text[] not null,
  
  -- Optional link to proposal if used for boosting
  proposal_tx_id text
);

-- Create indexes for performance
create index if not exists idx_airdrops_tx_hash on public.airdrops(tx_hash);
create index if not exists idx_airdrops_block_height on public.airdrops(block_height);
create index if not exists idx_airdrops_timestamp on public.airdrops(timestamp);
create index if not exists idx_airdrops_sender on public.airdrops(sender);
create index if not exists idx_airdrops_contract_identifier on public.airdrops(contract_identifier);
create index if not exists idx_airdrops_token_identifier on public.airdrops(token_identifier);
create index if not exists idx_airdrops_success on public.airdrops(success);
create index if not exists idx_airdrops_proposal_tx_id on public.airdrops(proposal_tx_id);
create index if not exists idx_airdrops_recipients on public.airdrops using gin(recipients);
create index if not exists idx_airdrops_created_at on public.airdrops(created_at);

-- Add updated_at trigger (reuse existing function)
create trigger handle_airdrops_updated_at
  before update on public.airdrops
  for each row
  execute function public.handle_updated_at();

-- Add row level security (RLS)
alter table public.airdrops enable row level security;

-- Create policy for authenticated users to read airdrops
create policy "Users can view airdrops" on public.airdrops
  for select using (auth.role() = 'authenticated');

-- Create policy for authenticated users to insert airdrops (for system/webhook use)
create policy "Authenticated users can insert airdrops" on public.airdrops
  for insert with check (auth.role() = 'authenticated');

-- Create policy for authenticated users to update airdrops (for system use)
create policy "Authenticated users can update airdrops" on public.airdrops
  for update using (auth.role() = 'authenticated');

-- Add comments for documentation
comment on table public.airdrops is 'Tracks airdrop transactions with high-level metadata';
comment on column public.airdrops.tx_hash is 'Unique blockchain transaction hash identifier';
comment on column public.airdrops.block_height is 'Blockchain block number where transaction was included';
comment on column public.airdrops.timestamp is 'When the transaction was processed (converted from Unix timestamp)';
comment on column public.airdrops.sender is 'Principal address of the airdrop distributor';
comment on column public.airdrops.contract_identifier is 'Full contract principal identifier';
comment on column public.airdrops.token_identifier is 'Full asset identifier for the airdropped token';
comment on column public.airdrops.success is 'Whether the transaction succeeded';
comment on column public.airdrops.total_amount_airdropped is 'Sum of all distributed amounts (as string for large numbers)';
comment on column public.airdrops.recipients is 'Array of all recipient principal addresses';
comment on column public.airdrops.proposal_tx_id is 'Transaction ID if this airdrop was used to boost a proposal (NULL if not used)';

-- Insert sample data from the provided example
INSERT INTO public.airdrops (
    tx_hash, 
    block_height, 
    timestamp, 
    sender, 
    contract_identifier, 
    token_identifier, 
    success, 
    total_amount_airdropped, 
    recipients, 
    proposal_tx_id
) VALUES (
    '0xb1d7fced703d87ff5229c3fb9649647173ab1c93438409b11e901ee850d1c30c',
    3506062,
    '2025-08-04 12:42:25+00',
    'STRZ4P1ABSVSZPC4HZ4GDAW834HHEHJMF65X5S6D',
    'ST1Q9YZ2NY4KVBB08E005HAK3FSM8S3RX2WARP9Q1.fast12-faktory',
    'ST1Q9YZ2NY4KVBB08E005HAK3FSM8S3RX2WARP9Q1.fast12-faktory::fast12',
    true,
    '11123',
    ARRAY[
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-STRZ4-X5S6D-ST1F3-MQWNJ',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-STH7H-1KB70-ST37D-49KYP',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-SPH7H-JYT2C-ST3C8-72V5H',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-SP1TA-P46F8-ST17B-8NHKS',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-SP37A-R7J9T-ST18F-R5XW4',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-SP2BD-2QB7M-ST1HY-9PH5H',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-STRZ4-X5S6D-ST1XM-BS1E6',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-ST2VW-A5DCP-ST108-SJBXF',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-ST2EM-XAPKY-ST3H8-F2M3K',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-ST349-BQF3W-STTGV-Z6X47',
        'ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-ST1M8-HQ3C0-ST11K-4S5DC'
    ],
    NULL
);
