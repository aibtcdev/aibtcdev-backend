-- Add quoted tweet linking fields to x_tweets table
-- This enables storing quoted posts as separate linked records

-- Add the new columns
ALTER TABLE x_tweets 
ADD COLUMN quoted_tweet_id TEXT,
ADD COLUMN quoted_tweet_db_id UUID;

-- Add foreign key constraint for quoted_tweet_db_id
-- This creates a self-referencing foreign key to link to other x_tweets records
ALTER TABLE x_tweets 
ADD CONSTRAINT fk_x_tweets_quoted_tweet_db_id 
FOREIGN KEY (quoted_tweet_db_id) 
REFERENCES x_tweets(id) 
ON DELETE SET NULL;

-- Add index for performance on quoted tweet lookups
CREATE INDEX idx_x_tweets_quoted_tweet_id ON x_tweets(quoted_tweet_id);
CREATE INDEX idx_x_tweets_quoted_tweet_db_id ON x_tweets(quoted_tweet_db_id);

-- Add comment explaining the purpose
COMMENT ON COLUMN x_tweets.quoted_tweet_id IS 'Twitter ID of the quoted tweet (for external reference)';
COMMENT ON COLUMN x_tweets.quoted_tweet_db_id IS 'Database ID of the quoted tweet record (for internal linking)';

