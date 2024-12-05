import asyncio
from services.twitter import TwitterService
from typing import TypedDict
from lib.db import TweetDB
from services.flow import execute_twitter_stream
from dotenv import load_dotenv
import os

# Custom type definition for user profile data
class UserProfile(TypedDict):
    name: str    # User's full name
    age: int     # User's age
    email: str   # User's email address

# Initialize database connection for tweet tracking
tweet_db = TweetDB()

# Load environment variables from .env file
load_dotenv()

# Get and parse whitelisted authors from environment variable
# Authors are expected to be comma-separated in the TWITTER_WHITELISTED env var
whitelist_authors_str = os.getenv('TWITTER_WHITELISTED', '')
whitelist_authors = whitelist_authors_str.split(',')
print("Whitelisted authors:", whitelist_authors)

async def process_mentions(twitter: TwitterService, user_id: str) -> None:
    """
    Process Twitter mentions for a specific user and handle responses based on author whitelist.
    
    Args:
        twitter (TwitterService): Instance of TwitterService for API interactions
        user_id (str): Twitter user ID to fetch mentions for
    
    Returns:
        None
    
    Raises:
        Exception: If there's an error processing mentions
    """
    try:
        # Fetch mentions from Twitter API
        mentions = await twitter.get_mentions_by_user_id(user_id)
        if not mentions:
            print("No mentions found")
            return

        for mention in mentions:
            # Extract relevant tweet data with fallback to empty string if None
            tweet_id = mention.id or ""
            author_id = mention.author_id or ""
            conversation_id = mention.conversation_id or ""
            text = mention.text or ""
            
            # Skip processing if we've already seen this tweet
            if tweet_db.is_tweet_seen(tweet_id):
                continue

            # Check if author is in whitelist and process accordingly
            print(f"Checking author {author_id} against whitelist {whitelist_authors}")
            if str(author_id) in whitelist_authors:
                print(f"\nProcessing whitelisted mention {tweet_id} from user {author_id}")
                await execute_agent(twitter, conversation_id, tweet_id, author_id, text)
            else:
                print(f"\nSkipping non-whitelisted mention {tweet_id} from user {author_id}")
            
            # Store tweet data in database for tracking
            tweet_data = {
                'tweet_id': tweet_id,
                'author_id': author_id,
                'text': text,
                'conversation_id': conversation_id
            }
            tweet_db.add_seen_tweet(tweet_data)
                
    except Exception as e:
        print(f"Error processing mentions: {str(e)}")
        raise

async def execute_agent(twitter: TwitterService, conversation_id: str, id: str, user_id: str, text: str) -> None:    
    try:
        # Set up default parameters
        account_index = "0"
        
        # Get conversation history if conversation_id exists
        history = []
        if conversation_id:
            conversation_tweets = tweet_db.get_conversation_tweets(conversation_id)
            # Format tweets into history format
            history = [
                {
                    "role": "user" if tweet["author_id"] != os.getenv("TWITTER_AUTOMATED_USER_ID") else "assistant",
                    "content": tweet["text"]
                }
                for tweet in conversation_tweets
                if tweet["text"]  # Filter out any tweets without text
            ]
        
        print(f"\nProcessing tweet {id} from user {user_id}")
        print(f"Tweet text: {text}")
        print(f"Conversation history: {len(history)} messages")
        
        response_content = None
        # Process the chat stream
        async for response in execute_twitter_stream(twitter_service=twitter, account_index=account_index, history=history, input_str=text):
            if response["type"] == "result":
                if response.get("content"):
                    print("\nFinal Response:", response["content"])
                    response_content = response["content"]
                elif response.get("reason"):
                    print("\nNo response generated. Reason:", response["reason"])
            elif response["type"] == "step":
                print("\nStep:", response["content"])
                if response["result"]:
                    print("Result:", response["result"])
        
        if response_content:
            # Post the response to Twitter
            response_tweet = await twitter.post_tweet(
                text=response_content,
                reply_in_reply_to_tweet_id=id
            )
            
            # Store the bot's response in the database
            if response_tweet and response_tweet.id:
                tweet_db.add_bot_response(
                    conversation_id=conversation_id,
                    original_tweet_id=id,
                    response_tweet_id=response_tweet.id,
                    response_text=response_content
                )
                print(f"\nStored bot response in database. Response tweet ID: {response_tweet.id}")
            
    except Exception as e:
        print(f"Error executing agent: {str(e)}")
        raise

async def periodic_mention_check(twitter: TwitterService, user_id: str) -> None:
    """
    Periodically check for new mentions and process them.
    
    Args:
        twitter (TwitterService): Instance of TwitterService for API interactions
        user_id (str): Twitter user ID to fetch mentions for
    
    Returns:
        None
    """
    while True:
        await process_mentions(twitter, user_id)
        # async for response in execute_twitter_stream(twitter, "41", [], "Get me token pricing for stacks in my wallet @aibtcdevagent"):
        #     if response["type"] == "result":
        #         if response.get("content"):
        #             print("\nFinal Response:", response["content"])
        #             response_content = response["content"]
        #         elif response.get("reason"):
        #             print("\nNo response generated. Reason:", response["reason"])
        #     elif response["type"] == "step":
        #         print("\nStep:", response["content"])
        #         if response["result"]:
        #             print("Result:", response["result"])
        
        # Wait for 2 minutes before next check
        await asyncio.sleep(2 * 60)

async def main():
    """
    Main entry point for the Twitter mention monitor.
    
    Returns:
        None
    """
    # Initialize Twitter client
    twitter = TwitterService(
        consumer_key=os.getenv("TWITTER_CONSUMER_KEY", ""),
        consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET", ""),
        client_id=os.getenv("TWITTER_CLIENT_ID", ""),
        client_secret=os.getenv("TWITTER_CLIENT_SECRET", ""),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN", ""),
        access_secret=os.getenv("TWITTER_ACCESS_SECRET", ""),
    )
    
    await twitter.initialize()

    USER_ID = os.getenv("TWITTER_AUTOMATED_USER_ID", "")
    
    print("Starting Twitter mention monitor...")
    print("Checking for new mentions every 2 minutes...")
    
    await periodic_mention_check(twitter, USER_ID)

if __name__ == "__main__":
    asyncio.run(main())