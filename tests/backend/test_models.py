"""Tests for backend models."""

from backend.models import QueueMessageBase, QueueMessageFilter, QueueMessageType


def test_queue_message_type_enum():
    """Test QueueMessageType enum values."""
    assert QueueMessageType.TWEET == "tweet"
    assert QueueMessageType.DAO == "dao"
    assert QueueMessageType.DAO_TWEET == "dao_tweet"
    assert QueueMessageType.DAO_PROPOSAL_VOTE == "dao_proposal_vote"

    # Test string conversion
    assert str(QueueMessageType.TWEET) == "tweet"
    assert str(QueueMessageType.DAO) == "dao"
    assert str(QueueMessageType.DAO_TWEET) == "dao_tweet"
    assert str(QueueMessageType.DAO_PROPOSAL_VOTE) == "dao_proposal_vote"


def test_queue_message_base_with_enum():
    """Test QueueMessageBase with QueueMessageType enum."""
    # Create a message with enum type
    message = QueueMessageBase(type=QueueMessageType.TWEET)
    assert message.type == QueueMessageType.TWEET

    # Test serialization/deserialization
    message_dict = message.model_dump()
    assert message_dict["type"] == "tweet"

    # Create from dict
    message2 = QueueMessageBase.model_validate({"type": "tweet"})
    assert message2.type == QueueMessageType.TWEET


def test_queue_message_filter_with_enum():
    """Test QueueMessageFilter with QueueMessageType enum."""
    # Create a filter with enum type
    filter_obj = QueueMessageFilter(type=QueueMessageType.DAO)
    assert filter_obj.type == QueueMessageType.DAO

    # Test serialization/deserialization
    filter_dict = filter_obj.model_dump()
    assert filter_dict["type"] == "dao"
