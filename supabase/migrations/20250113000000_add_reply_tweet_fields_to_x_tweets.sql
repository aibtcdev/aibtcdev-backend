-- Add reply tweet linking fields to x_tweets table
-- This enables storing reply posts as separate linked records

-- Add the new columns
ALTER TABLE x_tweets 
ADD COLUMN in_reply_to_user_id TEXT,
ADD COLUMN replied_to_tweet_id TEXT,
ADD COLUMN replied_to_tweet_db_id UUID;

-- Add foreign key constraint for replied_to_tweet_db_id
-- This creates a self-referencing foreign key to link to parent tweets
ALTER TABLE x_tweets 
ADD CONSTRAINT fk_x_tweets_replied_to_tweet_db_id 
FOREIGN KEY (replied_to_tweet_db_id) 
REFERENCES x_tweets(id) 
ON DELETE SET NULL;

-- Add indexes for performance on reply tweet lookups
CREATE INDEX idx_x_tweets_in_reply_to_user_id ON x_tweets(in_reply_to_user_id);
CREATE INDEX idx_x_tweets_replied_to_tweet_id ON x_tweets(replied_to_tweet_id);
CREATE INDEX idx_x_tweets_replied_to_tweet_db_id ON x_tweets(replied_to_tweet_db_id);

-- Add comments explaining the purpose
COMMENT ON COLUMN x_tweets.in_reply_to_user_id IS 'Twitter user ID being replied to';
COMMENT ON COLUMN x_tweets.replied_to_tweet_id IS 'Twitter ID of the parent tweet (for external reference)';
COMMENT ON COLUMN x_tweets.replied_to_tweet_db_id IS 'Database ID of the parent tweet record (for internal linking)';

