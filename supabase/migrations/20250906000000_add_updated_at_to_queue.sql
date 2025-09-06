-- Add updated_at column to queue table
-- This column will track when a queue message was last modified

-- Add the updated_at column
ALTER TABLE public.queue
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Create an index for efficient querying
CREATE INDEX IF NOT EXISTS idx_queue_updated_at ON public.queue(updated_at);

-- Add trigger to automatically update the updated_at column when row is modified
-- First create the trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for the queue table
CREATE TRIGGER handle_queue_updated_at
    BEFORE UPDATE ON public.queue
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- Add comment for documentation
COMMENT ON COLUMN public.queue.updated_at IS 'Timestamp of when the queue message was last updated';
