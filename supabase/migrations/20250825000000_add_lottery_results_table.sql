-- Create lottery_results table for tracking proposal voting lottery selections with quorum awareness
CREATE TABLE public.lottery_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    proposal_id UUID REFERENCES public.proposals(id) ON DELETE CASCADE,
    dao_id UUID REFERENCES public.daos(id) ON DELETE CASCADE,
    bitcoin_block_height INTEGER,
    bitcoin_block_hash TEXT,
    lottery_seed TEXT,
    
    -- Enhanced wallet tracking with token amounts
    selected_wallets JSONB DEFAULT '[]', -- Array of {"wallet_id": "uuid", "token_amount": "amount"}
    
    -- Quorum tracking fields
    liquid_tokens_at_creation TEXT, -- Total liquid supply from proposal
    quorum_threshold TEXT, -- Required tokens to meet quorum (15% of liquid_tokens)
    total_selected_tokens TEXT, -- Sum of selected wallet token amounts
    quorum_achieved BOOLEAN DEFAULT FALSE, -- Whether quorum was met
    quorum_percentage DECIMAL(5,4) DEFAULT 0.15, -- Quorum percentage (default 15%)
    
    -- Selection metadata
    total_eligible_wallets INTEGER,
    total_eligible_tokens TEXT, -- Sum of all available tokens
    selection_rounds INTEGER DEFAULT 1, -- How many lottery rounds were needed
    max_selections INTEGER DEFAULT 100, -- Safety cap for runaway selection
    
    -- Legacy field for backward compatibility
    selected_wallet_ids UUID[] DEFAULT '{}'
);

-- Add indexes for efficient queries
CREATE INDEX idx_lottery_results_proposal_id ON public.lottery_results(proposal_id);
CREATE INDEX idx_lottery_results_dao_id ON public.lottery_results(dao_id);
CREATE INDEX idx_lottery_results_bitcoin_block_height ON public.lottery_results(bitcoin_block_height);
CREATE INDEX idx_lottery_results_bitcoin_block_hash ON public.lottery_results(bitcoin_block_hash);
CREATE INDEX idx_lottery_results_quorum_achieved ON public.lottery_results(quorum_achieved);
CREATE INDEX idx_lottery_results_selected_wallets_gin ON public.lottery_results USING GIN (selected_wallets);

-- Add unique constraint to ensure one lottery result per proposal
CREATE UNIQUE INDEX idx_lottery_results_proposal_unique ON public.lottery_results(proposal_id);

-- Enable RLS (Row Level Security)
ALTER TABLE public.lottery_results ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (adjust based on your authentication system)
-- Allow read access to all authenticated users
CREATE POLICY "lottery_results_select_policy" ON public.lottery_results
    FOR SELECT USING (auth.role() = 'authenticated');

-- Allow insert/update/delete for service role (for system operations)
CREATE POLICY "lottery_results_insert_policy" ON public.lottery_results
    FOR INSERT WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "lottery_results_update_policy" ON public.lottery_results
    FOR UPDATE USING (auth.role() = 'service_role');

CREATE POLICY "lottery_results_delete_policy" ON public.lottery_results
    FOR DELETE USING (auth.role() = 'service_role');

-- Grant necessary permissions
GRANT ALL ON public.lottery_results TO service_role;
GRANT SELECT ON public.lottery_results TO authenticated;