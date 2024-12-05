import sqlite3
from typing import List, Dict, Any

class TweetDB:
    def __init__(self, db_path: str = "tweets.db"):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure the necessary tables exist and are properly migrated."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if the seen_tweets table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='seen_tweets';
            """)
            seen_tweets_exists = cursor.fetchone() is not None
            
            if not seen_tweets_exists:
                # Create new table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE seen_tweets (
                        tweet_id TEXT PRIMARY KEY,
                        author_id TEXT NOT NULL,
                        text TEXT,
                        conversation_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                # Check existing columns
                cursor.execute("PRAGMA table_info(seen_tweets)")
                columns = {col[1] for col in cursor.fetchall()}
                
                # Add new columns if they don't exist
                if 'text' not in columns:
                    cursor.execute("ALTER TABLE seen_tweets ADD COLUMN text TEXT")
                if 'conversation_id' not in columns:
                    cursor.execute("ALTER TABLE seen_tweets ADD COLUMN conversation_id TEXT")
            
            # Check if the bot_responses table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='bot_responses';
            """)
            bot_responses_exists = cursor.fetchone() is not None
            
            if not bot_responses_exists:
                # Create new table for bot responses
                cursor.execute("""
                    CREATE TABLE bot_responses (
                        response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id TEXT NOT NULL,
                        original_tweet_id TEXT NOT NULL,
                        response_tweet_id TEXT NOT NULL,
                        response_text TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES seen_tweets(conversation_id)
                    )
                """)
            
            conn.commit()
    
    def add_seen_tweet(self, tweet_data: Dict[str, Any]) -> None:
        """
        Add a tweet to the seen tweets table.
        
        Args:
            tweet_data: Dictionary containing tweet information with keys:
                - tweet_id: The ID of the tweet
                - author_id: The ID of the tweet's author
                - text: The content of the tweet
                - conversation_id: The ID of the conversation thread
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO seen_tweets 
                (tweet_id, author_id, text, conversation_id) 
                VALUES (?, ?, ?, ?)
                """,
                (
                    tweet_data['tweet_id'],
                    tweet_data['author_id'],
                    tweet_data.get('text'),  # Use get() for optional fields
                    tweet_data.get('conversation_id')
                )
            )
            conn.commit()
    
    def is_tweet_seen(self, tweet_id: str) -> bool:
        """Check if a tweet has been seen before."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM seen_tweets WHERE tweet_id = ?",
                (tweet_id,)
            )
            return cursor.fetchone() is not None
    
    def get_seen_tweets(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get the most recent seen tweets.
        
        Returns:
            List of dictionaries containing tweet information
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT tweet_id, author_id, text, conversation_id, created_at 
                FROM seen_tweets 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_conversation_tweets(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all tweets in a conversation thread.
        
        Args:
            conversation_id: The ID of the conversation to retrieve
            
        Returns:
            List of dictionaries containing tweet information
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT tweet_id, author_id, text, conversation_id, created_at 
                FROM seen_tweets 
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_tweets(self, days: int = 30) -> int:
        """Remove tweets older than specified days."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM seen_tweets WHERE created_at < datetime('now', ?)",
                (f'-{days} days',)
            )
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def add_bot_response(self, conversation_id: str, original_tweet_id: str, response_tweet_id: str, response_text: str) -> None:
        """
        Store a bot's response to a tweet.
        
        Args:
            conversation_id: The ID of the conversation thread
            original_tweet_id: The ID of the tweet being responded to
            response_tweet_id: The ID of the bot's response tweet
            response_text: The content of the bot's response
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO bot_responses 
                (conversation_id, original_tweet_id, response_tweet_id, response_text) 
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, original_tweet_id, response_tweet_id, response_text)
            )
            conn.commit()
