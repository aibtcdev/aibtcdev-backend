"""
Module for parsing narrative-style DAO creation requests.
"""

import re
from typing import Dict, Optional, Tuple
from pydantic import BaseModel

class NarrativeDAOParams(BaseModel):
    """Parameters extracted from narrative DAO creation request."""
    dao_name: str
    token_symbol: str
    token_supply: int
    mission: str
    description: str

class NarrativeParser:
    """Parser for narrative-style DAO creation requests."""
    
    # Regex patterns for parameter extraction
    PATTERNS = {
        'dao_name': r'create\s+(.*?)\s+DAO',
        'token_symbol': r'\$([A-Z]+)',
        'token_supply': r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M|billion|B)?(?:\s+\$[A-Z]+\s+tokens)',
        'mission': r'(?:,|with).*?(?=\.|$)',
        'description': r'(?<=\.).*$'
    }

    def __init__(self):
        """Initialize the parser with compiled regex patterns."""
        self.compiled_patterns = {
            key: re.compile(pattern, re.IGNORECASE)
            for key, pattern in self.PATTERNS.items()
        }

    def _clean_text(self, text: str) -> str:
        """Clean the input text for processing."""
        # Remove mention if present
        text = re.sub(r'\.?@\w+\s+', '', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text

    def _extract_token_supply(self, match: str) -> int:
        """Convert token supply string to integer."""
        # Extract just the numeric part using regex
        number_match = re.match(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', match)
        if not number_match:
            raise ValueError(f"Could not extract numeric value from {match}")
            
        # Remove commas and convert to float
        number = float(number_match.group(1).replace(',', ''))
        
        # Handle million/billion suffixes
        if 'million' in match.lower() or 'M' in match:
            number *= 1_000_000
        elif 'billion' in match.lower() or 'B' in match:
            number *= 1_000_000_000
            
        return int(number)

    def _extract_mission_description(self, text: str) -> Tuple[str, str]:
        """Extract mission and description from text."""
        mission_match = self.compiled_patterns['mission'].search(text)
        description_match = self.compiled_patterns['description'].search(text)
        
        mission = mission_match.group().strip(' ,.') if mission_match else ""
        description = description_match.group().strip() if description_match else ""
        
        # If no separate description, use entire text after DAO parameters
        if not description and mission:
            parts = mission.split('.')
            if len(parts) > 1:
                mission = parts[0].strip()
                description = '.'.join(parts[1:]).strip()
        
        return mission, description

    def parse(self, text: str) -> Optional[NarrativeDAOParams]:
        """
        Parse narrative text into DAO parameters.
        
        Args:
            text: The narrative DAO creation request text
            
        Returns:
            NarrativeDAOParams if successful, None if parsing fails
            
        Example:
            ".@aibtcdevagent create Stellar Forge DAO, with 400,000,000 $FORGE tokens, 
             drives starship propulsion and sustainable star-mining technologies. Through 
             decentralized governance, it empowers Galactic Smiths to lead space innovation."
        """
        cleaned_text = self._clean_text(text)
        
        # Extract basic parameters
        dao_name_match = self.compiled_patterns['dao_name'].search(cleaned_text)
        token_symbol_match = self.compiled_patterns['token_symbol'].search(cleaned_text)
        token_supply_match = self.compiled_patterns['token_supply'].search(cleaned_text)
        
        if not all([dao_name_match, token_symbol_match, token_supply_match]):
            return None
            
        # Extract and process values
        dao_name = dao_name_match.group(1).strip()
        token_symbol = token_symbol_match.group(1).strip()
        token_supply = self._extract_token_supply(token_supply_match.group())
        
        # Extract mission and description
        mission, description = self._extract_mission_description(cleaned_text)
        
        return NarrativeDAOParams(
            dao_name=dao_name,
            token_symbol=token_symbol,
            token_supply=token_supply,
            mission=mission,
            description=description
        )
