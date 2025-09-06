-- Add missing indexes on foreign key columns for improved query performance
-- This migration creates indexes on foreign key columns that don't already have them
-- Created: 2025-09-06

-- HOLDERS TABLE
-- Add indexes on foreign key columns that are missing
CREATE INDEX IF NOT EXISTS idx_holders_dao_id ON public.holders(dao_id);
CREATE INDEX IF NOT EXISTS idx_holders_token_id ON public.holders(token_id);
CREATE INDEX IF NOT EXISTS idx_holders_agent_id ON public.holders(agent_id);

-- KEYS TABLE
-- Add index on profile_id foreign key
CREATE INDEX IF NOT EXISTS idx_keys_profile_id ON public.keys(profile_id);

-- TELEGRAM_USERS TABLE
-- Add index on profile_id foreign key
CREATE INDEX IF NOT EXISTS idx_telegram_users_profile_id ON public.telegram_users(profile_id);

-- X_CREDS TABLE
-- Add index on dao_id foreign key
CREATE INDEX IF NOT EXISTS idx_x_creds_dao_id ON public.x_creds(dao_id);

-- X_TWEETS TABLE
-- Add index on author_id foreign key
CREATE INDEX IF NOT EXISTS idx_x_tweets_author_id ON public.x_tweets(author_id);

-- WALLETS TABLE
-- Add indexes on foreign key columns
CREATE INDEX IF NOT EXISTS idx_wallets_agent_id ON public.wallets(agent_id);
CREATE INDEX IF NOT EXISTS idx_wallets_secret_id ON public.wallets(secret_id);

-- QUEUE TABLE
-- Add index on dao_id foreign key (wallet_id already indexed)
CREATE INDEX IF NOT EXISTS idx_queue_dao_id ON public.queue(dao_id);

-- VETOS TABLE
-- Add index on profile_id foreign key (other FK indexes already exist)
CREATE INDEX IF NOT EXISTS idx_vetos_profile_id ON public.vetos(profile_id);

-- FEEDBACK TABLE
-- Add index on dao_id foreign key (profile_id and proposal_id already indexed)
CREATE INDEX IF NOT EXISTS idx_feedback_dao_id ON public.feedback(dao_id);

-- COMPOSITE INDEXES FOR COMMON QUERY PATTERNS
-- These indexes support common WHERE clauses that filter by multiple foreign keys

-- Holders by DAO and agent (useful for DAO member queries)
CREATE INDEX IF NOT EXISTS idx_holders_dao_agent ON public.holders(dao_id, agent_id);

-- Holders by DAO and token (useful for token distribution queries)
CREATE INDEX IF NOT EXISTS idx_holders_dao_token ON public.holders(dao_id, token_id);

-- Votes by DAO and agent (useful for agent voting history)
CREATE INDEX IF NOT EXISTS idx_votes_dao_agent ON public.votes(dao_id, agent_id);

-- Votes by proposal and agent (useful for checking if agent voted on proposal)
CREATE INDEX IF NOT EXISTS idx_votes_proposal_agent ON public.votes(proposal_id, agent_id);

-- Prompts by DAO and agent (useful for agent prompt queries)
CREATE INDEX IF NOT EXISTS idx_prompts_dao_agent ON public.prompts(dao_id, agent_id);

-- Queue items by DAO and processing status (useful for job processing)
CREATE INDEX IF NOT EXISTS idx_queue_dao_processed ON public.queue(dao_id, is_processed);

-- Wallets by profile and agent (useful for user wallet management)
CREATE INDEX IF NOT EXISTS idx_wallets_profile_agent ON public.wallets(profile_id, agent_id);

-- PERFORMANCE INDEXES FOR COMMON FILTERS
-- These indexes support common filtering patterns beyond just foreign keys

-- Queue items by processing status and creation time (for job queues)
CREATE INDEX IF NOT EXISTS idx_queue_processed_created ON public.queue(is_processed, created_at);

-- Proposals by status and DAO (for filtering active proposals)
CREATE INDEX IF NOT EXISTS idx_proposals_status_dao ON public.proposals(status, dao_id);

-- Votes by answer and proposal (for counting yes/no votes)
CREATE INDEX IF NOT EXISTS idx_votes_answer_proposal ON public.votes(answer, proposal_id);

-- X_tweets by worthy flag and creation time (for filtering worthy tweets)
CREATE INDEX IF NOT EXISTS idx_x_tweets_worthy_created ON public.x_tweets(is_worthy, created_at);

-- Agents by archived status and profile (for filtering active agents)
CREATE INDEX IF NOT EXISTS idx_agents_archived_profile ON public.agents(is_archived, profile_id);

-- COMMENTS FOR DOCUMENTATION
COMMENT ON INDEX idx_holders_dao_id IS 'Index on dao_id foreign key for efficient DAO member queries';
COMMENT ON INDEX idx_holders_token_id IS 'Index on token_id foreign key for efficient token holder queries';
COMMENT ON INDEX idx_holders_agent_id IS 'Index on agent_id foreign key for efficient agent holding queries';
COMMENT ON INDEX idx_keys_profile_id IS 'Index on profile_id foreign key for efficient API key lookups';
COMMENT ON INDEX idx_telegram_users_profile_id IS 'Index on profile_id foreign key for efficient Telegram user lookups';
COMMENT ON INDEX idx_x_creds_dao_id IS 'Index on dao_id foreign key for efficient X credentials lookups';
COMMENT ON INDEX idx_x_tweets_author_id IS 'Index on author_id foreign key for efficient tweet author queries';
COMMENT ON INDEX idx_wallets_agent_id IS 'Index on agent_id foreign key for efficient agent wallet queries';
COMMENT ON INDEX idx_wallets_secret_id IS 'Index on secret_id foreign key for efficient wallet secret lookups';
COMMENT ON INDEX idx_queue_dao_id IS 'Index on dao_id foreign key for efficient DAO job queue queries';
COMMENT ON INDEX idx_vetos_profile_id IS 'Index on profile_id foreign key for efficient user veto queries';
COMMENT ON INDEX idx_feedback_dao_id IS 'Index on dao_id foreign key for efficient DAO feedback queries';

-- Composite index comments
COMMENT ON INDEX idx_holders_dao_agent IS 'Composite index for queries filtering holders by both DAO and agent';
COMMENT ON INDEX idx_holders_dao_token IS 'Composite index for queries filtering holders by both DAO and token';
COMMENT ON INDEX idx_votes_dao_agent IS 'Composite index for agent voting history within specific DAOs';
COMMENT ON INDEX idx_votes_proposal_agent IS 'Composite index for checking if specific agent voted on specific proposal';
COMMENT ON INDEX idx_prompts_dao_agent IS 'Composite index for agent prompts within specific DAOs';
COMMENT ON INDEX idx_queue_dao_processed IS 'Composite index for DAO job queue processing status';
COMMENT ON INDEX idx_wallets_profile_agent IS 'Composite index for user wallet management queries';

-- Performance index comments
COMMENT ON INDEX idx_queue_processed_created IS 'Index for efficient job queue processing by status and time';
COMMENT ON INDEX idx_proposals_status_dao IS 'Index for filtering proposals by status within specific DAOs';
COMMENT ON INDEX idx_votes_answer_proposal IS 'Index for counting yes/no votes on proposals';
COMMENT ON INDEX idx_x_tweets_worthy_created IS 'Index for filtering worthy tweets by creation time';
COMMENT ON INDEX idx_agents_archived_profile IS 'Index for filtering active agents by profile';
