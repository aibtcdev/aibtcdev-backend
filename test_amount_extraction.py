#!/usr/bin/env python3
"""Test script to verify amount extraction from webhook data."""

from services.webhooks.chainhook.handlers.action_vote_handler import ActionVoteHandler
from services.webhooks.chainhook.models import Event

# Mock the test data from the webhook you provided
test_webhook_data = {
    "data": {
        "contract_identifier": "ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K.fast-action-proposal-voting",
        "topic": "print",
        "value": {
            "notification": "fast-action-proposal-voting/vote-on-action-proposal",
            "payload": {
                "amount": 4541549459041732,
                "contractCaller": "ST1B9N1SJPRK9D3H98FWGT8AXEGH8T4BH5P38Z4ZC",
                "proposalId": 44,
                "txSender": "ST1B9N1SJPRK9D3H98FWGT8AXEGH8T4BH5P38Z4ZC",
                "vote": True,
                "voter": "ST1B9N1SJPRK9D3H98FWGT8AXEGH8T4BH5P38Z4ZC",
                "voterUserId": 1,
            },
        },
    }
}


def create_mock_event(data):
    """Create a mock event object for testing."""

    class MockEvent:
        def __init__(self, data):
            self.type = "SmartContractEvent"
            self.data = data

    return MockEvent(data)


def test_amount_extraction():
    """Test the amount extraction from webhook data."""
    print("Testing amount extraction...")

    # Create handler
    handler = ActionVoteHandler()

    # Create mock event
    mock_event = create_mock_event(test_webhook_data["data"])
    events = [mock_event]

    # Test _get_vote_info_from_events
    print("\n1. Testing _get_vote_info_from_events:")
    vote_info = handler._get_vote_info_from_events(events)

    if vote_info:
        print(f"✓ Vote info extracted successfully: {vote_info}")
        print(f"✓ Amount from vote_info: {vote_info.get('amount')}")
        print(f"✓ Proposal ID: {vote_info.get('proposal_identifier')}")
        print(f"✓ Voter: {vote_info.get('voter')}")
        print(f"✓ Vote value: {vote_info.get('vote_value')}")
    else:
        print("✗ Failed to extract vote info")
        return False

    # Test _extract_amount directly
    print("\n2. Testing _extract_amount directly:")
    raw_amount = test_webhook_data["data"]["value"]["payload"]["amount"]
    print(f"Raw amount: {raw_amount} (type: {type(raw_amount)})")

    extracted_amount = handler._extract_amount(raw_amount)
    print(f"Extracted amount: {extracted_amount} (type: {type(extracted_amount)})")

    # Test with different amount formats
    print("\n3. Testing different amount formats:")
    test_amounts = [
        4541549459041732,  # int
        "4541549459041732",  # string
        "u4541549459041732",  # Clarity uint format
        None,  # None
        0,  # zero
        "0",  # zero string
    ]

    for test_amount in test_amounts:
        result = handler._extract_amount(test_amount)
        print(f"Input: {test_amount} ({type(test_amount)}) -> Output: {result}")

    print("\n4. Verification:")
    expected_amount = "4541549459041732"
    if vote_info and vote_info.get("amount") == expected_amount:
        print(f"✓ Amount extraction is working correctly: {expected_amount}")
        return True
    else:
        print(
            f"✗ Amount extraction failed. Expected: {expected_amount}, Got: {vote_info.get('amount') if vote_info else 'None'}"
        )
        return False


if __name__ == "__main__":
    test_amount_extraction()
