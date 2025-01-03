from typing import Dict, List, Optional
from pydantic import BaseModel

from lib.logger import configure_logger
from services.context_analyzer import TwitterContextAnalyzer
from services.rate_limiter import DAORateLimiter
from .dao_narrative_parser import NarrativeParser, NarrativeDAOParams
import time

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
        self.narrative_parser = NarrativeParser()

    async def analyze_request(
        self,
        tweet_text: str,
        user_id: str,
        user_tweets: List = None,
        user_profile: Dict = None
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
        # Try narrative format first
        narrative_result = self._try_parse_narrative(tweet_text)
        if narrative_result:
            return narrative_result

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

    def _try_parse_narrative(self, tweet_text: str) -> Optional[DAOAnalysisResult]:
        """Attempt to parse tweet as narrative format."""
        params = self.narrative_parser.parse(tweet_text)
        if not params:
            return None
            
        return DAOAnalysisResult(
            is_valid=True,
            reason="Successfully parsed narrative DAO creation request",
            parameters=DAOParameters(
                token_name=params.dao_name,
                token_symbol=params.token_symbol,
                token_max_supply=str(params.token_supply),
                token_decimals="6",
                token_description=params.description,
                mission=params.mission
            ),
            confidence_score=0.9 if params.description else 0.8
        )

    def _is_dao_request(self, text: str) -> bool:
        """Check if text contains DAO creation keywords."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.dao_keywords)

    def _extract_explicit_parameters(self, text: str) -> Dict:
        """Extract explicitly provided parameters from tweet text."""
        params = {}
        
        # Remove mentions and clean up text
        text = text.replace("@aibtcdevagent", "").strip()
        text = text.replace("@aibtcdev", "").strip()  # Remove other mentions
        text = text.replace(".", "").strip()  # Remove periods
        text = text.replace("'s", " ").strip()  # Remove possessives
        text = text.replace("'", "").strip()  # Remove other apostrophes
        
        # Convert to lowercase for processing but preserve original case for names
        text_lower = text.lower()
        
        # Define patterns for DAO/collective creation
        dao_patterns = [
            ("create dao ", ""),  # Simple create dao
            ("make dao ", ""),    # Simple make dao
            ("create a collective named ", ""),  # Named collective
            ("make a collective named ", ""),    # Named collective
        ]
        
        # Extract DAO name after any of our patterns
        dao_name = None
        remaining_text = None
        
        for pattern, prefix in dao_patterns:
            if pattern in text_lower:
                # Get text after the pattern
                remaining = text[text_lower.index(pattern) + len(pattern):].strip()
                if remaining:
                    # Split on whitespace to get the name
                    parts = remaining.split(None, 1)
                    dao_name = parts[0]
                    # Store any remaining text after the name
                    remaining_text = parts[1] if len(parts) > 1 else None
                    break
        
        if dao_name:
            # Use the exact case provided for token name
            params["token_name"] = dao_name
            params["token_symbol"] = dao_name.upper()[:4]  # Use first 4 chars as symbol
            params["token_max_supply"] = "1000000000"  # Default supply
            
            # Build description and mission using any additional context
            base_desc = f"A DAO token for {dao_name}"
            base_mission = f"Building a decentralized community around {dao_name}"
            
            if remaining_text:
                # Clean up common connecting words
                desc_text = remaining_text.strip()
                if desc_text.lower().startswith(("with", "and")):
                    desc_text = desc_text[4:].strip()  # Remove "with" or "and"
                
                params["token_description"] = f"{base_desc}: {desc_text}"
                params["mission"] = f"{base_mission}: {desc_text}"
            else:
                params["token_description"] = base_desc
                params["mission"] = base_mission
            
            return params
            
        # Common words to filter out, including typos and variations
        filter_words = {
            "that", "this", "with", "from", "about", "abut", "create", "make", 
            "dao", "collective", "thats", "for", "and", "the", "these", "those",
            "what", "where", "when", "why", "how", "which", "who", "whom",
            "your", "youre", "you", "its", "their", "there", "here"
        }
        
        # If no structured format found, extract keywords and generate parameters
        words = []
        for word in text_lower.split():
            # Remove any remaining punctuation
            word = ''.join(c for c in word if c.isalnum())
            if len(word) > 3 and word not in filter_words:
                words.append(word)
        
        if words:
            # Use the most relevant words to form a name
            name_words = words[:2]  # Take first two meaningful words
            dao_name = "".join(word.capitalize() for word in name_words)
            
            # Creative descriptions based on keywords
            descriptions = {
                "recruit": "Revolutionizing tech talent acquisition through decentralized collaboration",
                "recruiting": "Revolutionizing tech talent acquisition through decentralized collaboration",
                "dev": "Empowering developers to shape the future of technology",
                "devs": "Empowering developers to shape the future of technology",
                "develop": "Fostering innovation through collaborative development",
                "developer": "Building a thriving ecosystem for developer talent",
                "developers": "Building a thriving ecosystem for developer talent",
                "code": "Advancing the art of coding through decentralized governance",
                "coding": "Advancing the art of coding through decentralized governance",
                "program": "Transforming the landscape of software development",
                "programming": "Transforming the landscape of software development",
                "software": "Pioneering the next generation of software solutions",
                "tech": "Accelerating technological advancement through community-driven innovation",
                "technology": "Accelerating technological advancement through community-driven innovation",
                "build": "Creating revolutionary solutions through collective expertise",
                "building": "Creating revolutionary solutions through collective expertise",
                "engineer": "Uniting engineering talent to solve complex challenges",
                "engineering": "Uniting engineering talent to solve complex challenges",
            }
            
            # Find matching descriptions for our keywords
            matched_descriptions = []
            for word in words:
                if word in descriptions:
                    matched_descriptions.append(descriptions[word])
            
            # Generate creative description and mission
            if matched_descriptions:
                base_desc = matched_descriptions[0]
                if len(matched_descriptions) > 1:
                    mission = f"{matched_descriptions[1]} through decentralized community governance"
                else:
                    mission = f"Empowering the {' '.join(words)} community through decentralized governance"
            else:
                # Generic but contextual fallback
                activity = ' '.join(words)
                base_desc = f"Revolutionizing {activity} through decentralized collaboration"
                mission = f"Building a thriving ecosystem for {activity} innovation"
            
            # Generate parameters
            params["token_name"] = dao_name
            params["token_symbol"] = "".join(word[0].upper() for word in name_words)  # First letters
            params["token_max_supply"] = "1000000000"  # Default supply
            params["token_description"] = base_desc
            params["mission"] = mission
            
            return params
            
        # If still no parameters, use generic defaults
        timestamp = int(time.time())
        params["token_name"] = f"NewDAO{timestamp}"
        params["token_symbol"] = f"ND{timestamp % 1000}"
        params["token_max_supply"] = "1000000000"
        params["token_description"] = "A new decentralized autonomous organization"
        params["mission"] = "Building a decentralized community with shared goals"
        
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
