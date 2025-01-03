"""Tests for the DAO narrative parser."""

import pytest
from services.dao_narrative_parser import NarrativeParser, NarrativeDAOParams

@pytest.fixture
def parser():
    return NarrativeParser()

def test_parse_complete_narrative(parser):
    text = """
    .@aibtcdevagent create Stellar Forge DAO, with 400,000,000 $FORGE tokens, 
    drives starship propulsion and sustainable star-mining technologies. Through 
    decentralized governance, it empowers Galactic Smiths to lead space innovation.
    """
    
    result = parser.parse(text)
    
    assert isinstance(result, NarrativeDAOParams)
    assert result.dao_name == "Stellar Forge"
    assert result.token_symbol == "FORGE"
    assert result.token_supply == 400_000_000
    assert "starship propulsion" in result.mission.lower()
    assert "space innovation" in result.description.lower()

def test_parse_with_million_suffix(parser):
    text = ".@aibtcdevagent create Test DAO, with 1M $TEST tokens, simple mission."
    result = parser.parse(text)
    
    assert result.token_supply == 1_000_000

def test_parse_with_billion_suffix(parser):
    text = ".@aibtcdevagent create Test DAO, with 1B $TEST tokens, simple mission."
    result = parser.parse(text)
    
    assert result.token_supply == 1_000_000_000

def test_parse_with_commas(parser):
    text = ".@aibtcdevagent create Test DAO, with 1,000,000 $TEST tokens, simple mission."
    result = parser.parse(text)
    
    assert result.token_supply == 1_000_000

def test_parse_invalid_format(parser):
    text = "This is not a valid DAO creation request"
    result = parser.parse(text)
    
    assert result is None

def test_parse_missing_symbol(parser):
    text = ".@aibtcdevagent create Test DAO, with 1M tokens, simple mission."
    result = parser.parse(text)
    
    assert result is None

def test_parse_missing_supply(parser):
    text = ".@aibtcdevagent create Test DAO, with $TEST tokens, simple mission."
    result = parser.parse(text)
    
    assert result is None
