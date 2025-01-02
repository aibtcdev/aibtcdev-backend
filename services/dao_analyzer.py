from typing import Dict, List, Optional
from pydantic import BaseModel

from lib.logger import configure_logger
from services.context_analyzer import TwitterContextAnalyzer
from services.rate_limiter import DAORateLimiter

logger = configure_logger(__name__)


class DAOParameters(BaseModel):
    """Parameters for DAO creation."""
    token_symbol: str
    token_name: str
    token_description: str
    token_max_supply: str
    token_decimals: str = "6"
    mission: str


class DAOAnalysisResult(BaseModel):
    """Result of DAO creation request analysis."""
    is_valid: bool
    reason: str
    parameters: Optional[DAOParameters] = None
    confidence_score: float


class DAORequestAnalyzer:
    """Analyzer for DAO creation requests."""

    def __init__(self):
        """Initialize the DAO request analyzer."""
        self.context_analyzer = TwitterContextAnalyzer()
        self.rate_limiter = DAORateLimiter()
        self.dao_keywords = [
            "dao", "collective", "make dao", "create dao",
            "make collective", "create collective"
        ]

    async def analyze_request(
        self,
        tweet_text: str,
        user_id: str,
        user_tweets: List,
        user_profile: Dict
    ) -> DAOAnalysisResult:
        """
        Analyze a DAO creation request.

        Args:
            tweet_text: The text of the tweet
            user_id: Twitter user ID
            user_tweets: List of user's recent tweets
            user_profile: User's profile information

        Returns:
            Analysis result with validation and parameters
        """
        # Check rate limit first
        if not self.rate_limiter.check_rate_limit(user_id):
            return DAOAnalysisResult(
                is_valid=False,
                reason="Rate limit exceeded for DAO creation",
                confidence_score=1.0
            )

        # Check if this is a DAO request
        if not self._is_dao_request(tweet_text):
            return DAOAnalysisResult(
                is_valid=False,
                reason="Not a DAO creation request",
                confidence_score=0.8
            )

        # Analyze context
        tweet_context = self.context_analyzer.analyze_tweets(user_tweets)
        profile_context = self.context_analyzer.analyze_profile(user_profile)
        
        # Extract parameters from tweet
        explicit_params = self._extract_explicit_parameters(tweet_text)
        
        # If minimal info, use context to generate parameters
        if self._is_minimal_info(explicit_params):
            context_params = self.context_analyzer.extract_relevant_info({
                **tweet_context,
                **profile_context
            })
            dao_params = self._merge_parameters(explicit_params, context_params)
        else:
            dao_params = explicit_params

        # Validate final parameters
        try:
            parameters = DAOParameters(**dao_params)
            return DAOAnalysisResult(
                is_valid=True,
                reason="Valid DAO creation request",
                parameters=parameters,
                confidence_score=0.9
            )
        except Exception as e:
            logger.error(f"Parameter validation failed: {str(e)}")
            return DAOAnalysisResult(
                is_valid=False,
                reason=f"Invalid parameters: {str(e)}",
                confidence_score=0.7
            )

    def _is_dao_request(self, text: str) -> bool:
        """Check if text contains DAO creation keywords."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.dao_keywords)

    def _extract_explicit_parameters(self, text: str) -> Dict:
        """Extract explicitly provided parameters from tweet text."""
        params = {}
        
        # Remove mentions and common prefixes
        text = text.replace("@aibtcdevagent", "").lower().strip()
        text = text.replace("create dao", "").strip()
        text = text.replace("make dao", "").strip()
        text = text.replace(".", "").strip()  # Remove leading periods
        
        # First try structured format
        lines = text.split('\n')
        for line in lines:
            line = line.strip().lower()
            if "name:" in line:
                params["token_name"] = line.split("name:")[1].strip()
            elif "symbol:" in line:
                params["token_symbol"] = line.split("symbol:")[1].strip()
            elif "supply:" in line:
                params["token_max_supply"] = line.split("supply:")[1].strip()
            elif "description:" in line:
                params["token_description"] = line.split("description:")[1].strip()
            elif "mission:" in line:
                params["mission"] = line.split("mission:")[1].strip()
                
        # If no structured params found, try to extract from simple format
        if not params and text:
            # Split remaining text into words
            words = text.split()
            if words:
                # First word after "create dao" is likely the name
                name = words[0].strip()
                if name:
                    params["token_name"] = name.title()  # Capitalize first letter
                    params["token_symbol"] = name.upper()[:4]  # Use first 4 chars as symbol
                    params["token_max_supply"] = "1000000000"  # Default supply
                    
                    # Join remaining words as description/mission
                    if len(words) > 1:
                        desc = " ".join(words[1:])
                        params["token_description"] = f"A DAO token for {desc}"
                        params["mission"] = f"Building a decentralized community around {desc}"
                    else:
                        params["token_description"] = f"A DAO token for {name}"
                        params["mission"] = f"Building a decentralized community"

        return params

    def _is_minimal_info(self, params: Dict) -> bool:
        """Check if only minimal information was provided."""
        required_fields = {"token_name", "token_symbol", "token_description", "mission"}
        return len(set(params.keys()) & required_fields) < 3

    def _merge_parameters(self, explicit: Dict, context: Dict) -> Dict:
        """Merge explicit and context-derived parameters."""
        merged = context.copy()  # Start with context-derived params
        
        # Override with any explicit parameters
        for key, value in explicit.items():
            if value:  # Only override if value is not empty
                merged[key] = value

        # Ensure required fields
        if "token_decimals" not in merged:
            merged["token_decimals"] = "6"
        
        if "token_max_supply" not in merged:
            merged["token_max_supply"] = "1000000000"

        return merged
