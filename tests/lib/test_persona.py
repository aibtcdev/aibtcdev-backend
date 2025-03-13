from typing import Any, Dict
from unittest.mock import Mock

import pytest

from backend.models import Agent
from lib.logger import configure_logger
from lib.persona import generate_persona, generate_static_persona

logger = configure_logger(__name__)


@pytest.fixture
def mock_agent() -> Agent:
    """Fixture providing a mock Agent instance."""
    agent = Mock(spec=Agent)
    agent.name = "TestBot"
    agent.backstory = "A test bot with a simple backstory"
    agent.role = "Testing assistant"
    agent.goal = "Help with testing"
    return agent


def test_generate_persona(mock_agent: Agent) -> None:
    """Test persona generation with a mock agent."""
    persona = generate_persona(mock_agent)

    # Check that the persona is a string
    assert isinstance(persona, str)

    # Check that agent attributes are included in the persona
    assert mock_agent.name in persona
    assert mock_agent.backstory in persona
    assert mock_agent.role in persona
    assert mock_agent.goal in persona

    # Check for required sections
    required_sections = [
        "Knowledge:",
        "Extensions:",
        "Disclaimer:",
        "Style:",
        "Boundaries:",
    ]
    for section in required_sections:
        assert section in persona


def test_generate_static_persona() -> None:
    """Test static persona generation."""
    persona = generate_static_persona()

    # Check that the persona is a string
    assert isinstance(persona, str)

    # Check for default name
    assert "AI Assistant" in persona

    # Check for required sections
    required_sections = [
        "Role:",
        "Goal:",
        "Knowledge:",
        "Extensions:",
        "Disclaimer:",
        "Style:",
        "Boundaries:",
    ]
    for section in required_sections:
        assert section in persona

    # Check for specific content
    assert "Stacks blockchain" in persona
    assert "not a licensed financial advisor" in persona
    assert "do not support or endorse illicit activities" in persona


def test_persona_formatting() -> None:
    """Test persona formatting rules."""
    persona = generate_static_persona()

    # Check that the persona doesn't contain emojis
    # This is a basic check - you might want to add more comprehensive emoji detection
    common_emojis = ["😊", "👍", "🚀", "💰", "📈"]
    for emoji in common_emojis:
        assert emoji not in persona

    # Check that markdown syntax isn't used
    markdown_elements = ["##", "**", "__", "```", "==="]
    for element in markdown_elements:
        assert element not in persona


def test_persona_content_consistency(mock_agent: Agent) -> None:
    """Test that generated personas maintain consistent content across calls."""
    persona1 = generate_persona(mock_agent)
    persona2 = generate_persona(mock_agent)
    assert persona1 == persona2

    static_persona1 = generate_static_persona()
    static_persona2 = generate_static_persona()
    assert static_persona1 == static_persona2


def test_persona_security_elements() -> None:
    """Test that personas include necessary security-related content."""
    persona = generate_static_persona()

    security_elements = [
        "security best practices",
        "keep private keys secure",
        "do their own research",
    ]

    for element in security_elements:
        assert element.lower() in persona.lower()


def test_persona_with_empty_agent_fields(mock_agent: Agent) -> None:
    """Test persona generation with empty agent fields."""
    mock_agent.name = ""
    mock_agent.backstory = ""
    mock_agent.role = ""
    mock_agent.goal = ""

    persona = generate_persona(mock_agent)

    # Check that the persona is still generated and contains core elements
    assert isinstance(persona, str)
    assert "Knowledge:" in persona
    assert "Extensions:" in persona
    assert "Disclaimer:" in persona
