-- Add deduplication constraint to queue table to prevent 5x message multiplication
-- This migration adds a unique constraint to prevent duplicate unprocessed messages

-- Add a computed column for message content hash to enable efficient deduplication
ALTER TABLE public.queue 
ADD COLUMN IF NOT EXISTS message_hash TEXT 
GENERATED ALWAYS AS (md5(message::text)) STORED;

-- Create index for the message hash for performance
CREATE INDEX IF NOT EXISTS idx_queue_message_hash ON public.queue(message_hash);

-- Create unique constraint to prevent duplicate unprocessed messages
-- This constraint ensures that for any combination of (type, dao_id, wallet_id, message_hash), 
-- there can only be one unprocessed message at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_unique_unprocessed_message
ON public.queue (type, dao_id, wallet_id, message_hash)
WHERE is_processed = false;

-- Add partial index for efficient queries on unprocessed messages
CREATE INDEX IF NOT EXISTS idx_queue_unprocessed_by_type_dao 
ON public.queue (type, dao_id, created_at)
WHERE is_processed = false;

-- Add comments for documentation
COMMENT ON COLUMN public.queue.message_hash IS 'MD5 hash of the message content for deduplication';
COMMENT ON INDEX public.idx_queue_unique_unprocessed_message IS 'Prevents duplicate unprocessed messages with same type, DAO, wallet, and content';

-- Create function to handle duplicate message insertions gracefully
CREATE OR REPLACE FUNCTION public.handle_duplicate_queue_message()
RETURNS TRIGGER AS $$
BEGIN
    -- If a duplicate is detected (this would be caught by the unique constraint),
    -- we could handle it here, but the constraint itself will prevent the insert
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Optional: Add logging for duplicate attempts (uncomment if you want to track these)
-- CREATE OR REPLACE FUNCTION public.log_duplicate_queue_attempt()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     INSERT INTO public.queue_duplicate_log (attempted_type, attempted_dao_id, attempted_message_hash, attempted_at)
--     VALUES (NEW.type, NEW.dao_id, NEW.message_hash, NOW());
--     RETURN NULL; -- Don't actually insert the duplicate
-- END;
-- $$ LANGUAGE plpgsql;