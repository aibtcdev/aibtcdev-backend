from datetime import datetime
from typing import Dict, List, Optional
from pytwitter.models import Tweet, User, TweetEntities

from lib.logger import configure_logger

logger = configure_logger(__name__)

class TwitterContextAnalyzer:
    def __init__(self):
        """Initialize the Twitter context analyzer."""
        self.relevant_keywords = [
            "blockchain", "crypto", "web3", "dao", "defi", "nft",
            "bitcoin", "stacks", "community", "token", "governance"
        ]

    def analyze_tweets(self, tweets: List[Tweet], max_age_days: int = 7) -> Dict:
        """
        Analyze a list of tweets for relevant context.

        Args:
            tweets: List of tweets to analyze
            max_age_days: Maximum age of tweets to consider for weighting

        Returns:
            Dictionary containing analyzed context
        """
        context = {
            "interests": {},
            "engagement_metrics": {},
            "common_topics": set(),
            "mentioned_users": set(),
            "hashtags": set()
        }

        now = datetime.utcnow()
        
        for tweet in tweets:
            # Parse created_at string to datetime
            try:
                # Remove timezone info if present (e.g., +00:00)
                created_at_str = tweet.created_at.split('+')[0].split('Z')[0]
                tweet_datetime = datetime.fromisoformat(created_at_str)
                # Calculate tweet age and weight
                tweet_age = (now - tweet_datetime).days
                weight = 1.0 if tweet_age > max_age_days else (max_age_days - tweet_age) / max_age_days

                # Analyze text content
                self._analyze_text_content(tweet.text, context, weight)
                
                # Analyze entities if available
                if hasattr(tweet, "entities"):
                    self._analyze_entities(tweet.entities, context)

                # Analyze metrics if available
                if hasattr(tweet, "public_metrics"):
                    self._analyze_metrics(tweet.public_metrics, context, weight)
            except (AttributeError, ValueError) as e:
                logger.warning(f"Error processing tweet timestamp: {e}")
                continue

        return context

    def analyze_profile(self, profile: Optional[User]) -> Dict:
        """
        Analyze a user's profile for relevant context.

        Args:
            profile: User profile to analyze

        Returns:
            Dictionary containing analyzed context
        """
        context = {
            "interests": {},
            "profile_topics": set(),
            "profile_links": set()
        }

        if profile is not None and hasattr(profile, "description") and profile.description:
            self._analyze_text_content(profile.description, context, weight=1.5)

        if profile is not None and hasattr(profile, "entities"):
            self._analyze_entities(profile.entities, context)

        return context

    def extract_relevant_info(self, context: Dict) -> Dict:
        """
        Extract the most relevant information from analyzed context.

        Args:
            context: Analyzed context dictionary

        Returns:
            Dictionary containing relevant DAO parameters
        """
        dao_params = {
            "suggested_name": None,
            "suggested_symbol": None,
            "suggested_description": None,
            "suggested_mission": None
        }

        # Extract most common topics for name/symbol suggestions
        if context.get("common_topics"):
            top_topics = sorted(context["common_topics"], 
                              key=lambda x: context["interests"].get(x, 0), 
                              reverse=True)
            if top_topics:
                dao_params["suggested_name"] = f"{top_topics[0].title()} DAO"
                dao_params["suggested_symbol"] = f"${top_topics[0][:4].upper()}"

        # Generate description and mission from interests
        if context.get("interests"):
            top_interests = sorted(context["interests"].items(), 
                                 key=lambda x: x[1], 
                                 reverse=True)[:3]
            interests_text = ", ".join(interest[0].title() for interest in top_interests)
            
            dao_params["suggested_description"] = (
                f"A community-driven DAO focused on {interests_text}"
            )
            dao_params["suggested_mission"] = (
                f"Building a decentralized future through {interests_text}"
            )

        return dao_params

    def _analyze_text_content(self, text: str, context: Dict, weight: float = 1.0) -> None:
        """Analyze text content for relevant information."""
        words = text.lower().split()
        
        for word in words:
            if word in self.relevant_keywords:
                context["interests"][word] = context["interests"].get(word, 0) + weight

    def _analyze_entities(self, entities, context: Dict) -> None:
        """Analyze tweet entities for additional context."""
        if hasattr(entities, "hashtags") and entities.hashtags:
            for hashtag in entities.hashtags:
                if hasattr(hashtag, "tag"):
                    hashtag_text = hashtag.tag.lower()
                    context["hashtags"].add(hashtag_text)
                    if hashtag_text in self.relevant_keywords:
                        context["common_topics"].add(hashtag_text)

        if hasattr(entities, "mentions") and entities.mentions:
            for mention in entities.mentions:
                if hasattr(mention, "username"):
                    context["mentioned_users"].add(mention.username)

    def _analyze_metrics(self, metrics, context: Dict, weight: float = 1.0) -> None:
        """Analyze tweet metrics for engagement patterns."""
        # Initialize engagement_metrics if not present
        if "engagement_metrics" not in context:
            context["engagement_metrics"] = {}
            
        # Handle TweetPublicMetrics object
        if hasattr(metrics, "like_count"):
            context["engagement_metrics"]["like_count"] = context["engagement_metrics"].get("like_count", 0) + (metrics.like_count or 0) * weight
        if hasattr(metrics, "reply_count"):    
            context["engagement_metrics"]["reply_count"] = context["engagement_metrics"].get("reply_count", 0) + (metrics.reply_count or 0) * weight
        if hasattr(metrics, "retweet_count"):
            context["engagement_metrics"]["retweet_count"] = context["engagement_metrics"].get("retweet_count", 0) + (metrics.retweet_count or 0) * weight
        if hasattr(metrics, "quote_count"):
            context["engagement_metrics"]["quote_count"] = context["engagement_metrics"].get("quote_count", 0) + (metrics.quote_count or 0) * weight
