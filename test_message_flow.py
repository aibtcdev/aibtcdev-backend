#!/usr/bin/env python3
"""
Local test file to understand message flow between action_concluder_handler and tweet_task.

This file simulates the data flow and shows what message objects look like at each step.
"""

import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional
from uuid import UUID, uuid4

# Add the project root to Python path so we can import modules
sys.path.append('.')

from lib.utils import create_message_chunks, strip_metadata_section


@dataclass
class MockProposal:
    """Mock proposal object for testing."""
    id: str
    proposal_id: int
    content: str
    passed: bool
    votes_for: str = "1000"
    votes_against: str = "500"
    liquid_tokens: str = "2000"
    vote_start: int = 12345
    vote_end: int = 12500


@dataclass
class MockDao:
    """Mock DAO object for testing."""
    id: str
    name: str


@dataclass
class MockQueueMessage:
    """Mock queue message object for testing."""
    id: str
    dao_id: str
    type: str
    message: Dict
    is_processed: bool = False


class MessageFlowTester:
    """Test class to simulate the message flow."""

    def __init__(self):
        self.mock_dao = MockDao(
            id=str(uuid4()),
            name="Test DAO"
        )
        self.api_base_url = "https://api.aibtcdev.com"

    def create_test_proposal(self, content: str, passed: bool = True) -> MockProposal:
        """Create a test proposal."""
        return MockProposal(
            id=str(uuid4()),
            proposal_id=42,
            content=content,
            passed=passed
        )

    def simulate_action_concluder_handler(self, proposal: MockProposal) -> MockQueueMessage:
        """Simulate what action_concluder_handler does when creating tweet messages."""
        print("🔄 SIMULATING ACTION CONCLUDER HANDLER")
        print("=" * 60)
        
        # Step 1: Clean the message content (remove metadata)
        raw_message = proposal.content
        clean_message = strip_metadata_section(raw_message)
        
        print(f"📝 Raw proposal content:")
        print(f"   {raw_message[:100]}..." if len(raw_message) > 100 else f"   {raw_message}")
        print()
        
        print(f"🧹 Cleaned message content:")
        print(f"   {clean_message[:100]}..." if len(clean_message) > 100 else f"   {clean_message}")
        print()

        if proposal.passed:
            # Step 2: Create follow-up message content for passed proposals
            proposal_url = f"{self.api_base_url}/proposals/{proposal.id}"
            follow_up_message = (
                f"This message was approved by proposal #{proposal.proposal_id} of {self.mock_dao.name}.\n\n"
                f"1,000 DAO tokens has been rewarded to the submitter.\n\n"
                f"View proposal details: {proposal_url}"
            )
            
            print(f"✅ Follow-up message for passed proposal:")
            print(f"   {follow_up_message}")
            print()

            # Step 3: Create main chunks
            main_chunks = create_message_chunks(clean_message, add_indices=True)
            
            print(f"📦 Main message chunks ({len(main_chunks)}):")
            for i, chunk in enumerate(main_chunks, 1):
                print(f"   Chunk {i}: {chunk}")
            print()

            # Step 4: Add follow-up chunk
            follow_up_chunk = f"({len(main_chunks) + 1}/{len(main_chunks) + 1}) {follow_up_message}"
            message_chunks = main_chunks + [follow_up_chunk]
            
            print(f"🔗 Final message chunks with follow-up ({len(message_chunks)}):")
            for i, chunk in enumerate(message_chunks, 1):
                print(f"   Final Chunk {i}: {chunk[:100]}..." if len(chunk) > 100 else f"   Final Chunk {i}: {chunk}")
            print()

        else:
            # For failed proposals, just create main chunks
            message_chunks = create_message_chunks(clean_message, add_indices=True)
            print(f"❌ Message chunks for failed proposal ({len(message_chunks)}):")
            for i, chunk in enumerate(message_chunks, 1):
                print(f"   Chunk {i}: {chunk}")
            print()

        # Step 5: Create queue message structure
        queue_message_data = {
            "message": message_chunks,
            "total_chunks": len(message_chunks)
        }
        
        queue_message = MockQueueMessage(
            id=str(uuid4()),
            dao_id=self.mock_dao.id,
            type="tweet",
            message=queue_message_data
        )

        print(f"📨 Created queue message structure:")
        print(f"   Message ID: {queue_message.id}")
        print(f"   DAO ID: {queue_message.dao_id}")
        print(f"   Type: {queue_message.type}")
        print(f"   Message format: {type(queue_message.message)}")
        print(f"   Total chunks: {queue_message.message.get('total_chunks', 'N/A')}")
        print()

        return queue_message

    def simulate_tweet_task_processing(self, queue_message: MockQueueMessage) -> Dict:
        """Simulate what tweet_task does when processing queue messages."""
        print("🐦 SIMULATING TWEET TASK PROCESSING")
        print("=" * 60)
        
        # Step 1: Validate message structure
        print(f"🔍 Validating message structure:")
        print(f"   Message is dict: {isinstance(queue_message.message, dict)}")
        print(f"   Has 'message' key: {'message' in queue_message.message}")
        
        if 'message' in queue_message.message:
            tweet_data = queue_message.message['message']
            print(f"   Tweet data type: {type(tweet_data)}")
            print(f"   Is list (chunked format): {isinstance(tweet_data, list)}")
            print(f"   Is string (legacy format): {isinstance(tweet_data, str)}")
            print()

            # Step 2: Process based on format
            if isinstance(tweet_data, list):
                return self._simulate_chunked_processing(queue_message, tweet_data)
            elif isinstance(tweet_data, str):
                return self._simulate_legacy_processing(queue_message, tweet_data)
            else:
                print(f"❌ Unsupported tweet data format: {type(tweet_data)}")
                return {"success": False, "error": "Unsupported format"}
        else:
            print(f"❌ No 'message' key found in queue message")
            return {"success": False, "error": "No message key"}

    def _simulate_chunked_processing(self, queue_message: MockQueueMessage, chunks: List[str]) -> Dict:
        """Simulate processing of chunked message format."""
        print(f"📦 Processing chunked format with {len(chunks)} chunks:")
        
        # Check if chunks have thread indices
        has_indices = len(chunks) > 1 and any("(" in chunk and "/" in chunk and ")" in chunk for chunk in chunks)
        print(f"   Has thread indices: {has_indices}")
        print()

        tweets_sent = 0
        previous_tweet_id = None
        
        for index, chunk in enumerate(chunks):
            print(f"   Processing chunk {index + 1}/{len(chunks)}:")
            print(f"   📝 Content: {chunk}")
            print(f"   📏 Length: {len(chunk)} characters")
            
            # Simulate image URL extraction
            has_image = "http" in chunk and any(ext in chunk.lower() for ext in ['.jpg', '.png', '.gif', '.webp'])
            if has_image:
                print(f"   🖼️  Image detected in chunk")
            
            # Simulate tweet posting
            simulated_tweet_id = f"tweet_{queue_message.id}_{index + 1}"
            tweets_sent += 1
            previous_tweet_id = simulated_tweet_id
            
            print(f"   ✅ Simulated tweet posted: {simulated_tweet_id}")
            if index > 0:
                print(f"   🔗 Threaded to previous tweet")
            print()

        result = {
            "success": True,
            "message": f"Successfully sent {tweets_sent}/{len(chunks)} tweet chunks",
            "tweet_id": previous_tweet_id,
            "dao_id": queue_message.dao_id,
            "tweets_sent": tweets_sent,
            "chunks_processed": len(chunks),
            "format": "chunked"
        }

        print(f"✅ Chunked processing result:")
        print(f"   {json.dumps(result, indent=2)}")
        print()

        return result

    def _simulate_legacy_processing(self, queue_message: MockQueueMessage, tweet_text: str) -> Dict:
        """Simulate processing of legacy string format."""
        print(f"📜 Processing legacy format:")
        print(f"   Content: {tweet_text[:100]}..." if len(tweet_text) > 100 else f"   Content: {tweet_text}")
        print(f"   Length: {len(tweet_text)} characters")
        print()

        # Simulate text splitting if needed
        chunks = self._split_text_into_chunks(tweet_text)
        print(f"   Split into {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks, 1):
            print(f"     Chunk {i}: {chunk}")
        print()

        # Simulate processing each chunk
        tweets_sent = len(chunks)
        simulated_tweet_id = f"tweet_{queue_message.id}_final"

        result = {
            "success": True,
            "message": f"Successfully sent {tweets_sent}/{len(chunks)} tweet chunks",
            "tweet_id": simulated_tweet_id,
            "dao_id": queue_message.dao_id,
            "tweets_sent": tweets_sent,
            "chunks_processed": len(chunks),
            "format": "legacy"
        }

        print(f"✅ Legacy processing result:")
        print(f"   {json.dumps(result, indent=2)}")
        print()

        return result

    def _split_text_into_chunks(self, text: str, limit: int = 280) -> List[str]:
        """Split text into chunks (copy of the method from tweet_task)."""
        words = text.split()
        chunks = []
        current = ""
        for word in words:
            if len(current) + len(word) + (1 if current else 0) <= limit:
                current = f"{current} {word}".strip()
            else:
                if current:
                    chunks.append(current)
                current = word
        if current:
            chunks.append(current)
        return chunks

    def run_full_flow_test(self, proposal_content: str, proposal_passed: bool = True):
        """Run a complete end-to-end test of the message flow."""
        print("🚀 STARTING FULL MESSAGE FLOW TEST")
        print("=" * 80)
        print(f"🎯 Test scenario: {'PASSED' if proposal_passed else 'FAILED'} proposal")
        print(f"📄 Proposal content length: {len(proposal_content)} characters")
        print()

        # Step 1: Create test proposal
        proposal = self.create_test_proposal(proposal_content, proposal_passed)
        
        # Step 2: Simulate action concluder handler
        queue_message = self.simulate_action_concluder_handler(proposal)
        
        # Step 3: Simulate tweet task processing
        result = self.simulate_tweet_task_processing(queue_message)
        
        print("🏁 FINAL RESULTS")
        print("=" * 60)
        print(f"✅ Test completed successfully: {result.get('success', False)}")
        print(f"📊 Processing format used: {result.get('format', 'unknown')}")
        print(f"📨 Total tweets that would be sent: {result.get('tweets_sent', 0)}")
        print(f"📦 Total chunks processed: {result.get('chunks_processed', 0)}")
        print(f"🆔 Final tweet ID: {result.get('tweet_id', 'N/A')}")
        print()

        return result


def main():
    """Run various test scenarios."""
    tester = MessageFlowTester()
    
    # Test 1: Short proposal that passes
    print("TEST 1: Short Passed Proposal")
    print("=" * 80)
    short_content = "We should implement a new stacking mechanism for better rewards distribution. This will benefit all DAO members."
    tester.run_full_flow_test(short_content, proposal_passed=True)
    
    print("\n" * 2)
    
    # Test 2: Long proposal that passes (will be chunked)
    print("TEST 2: Long Passed Proposal")
    print("=" * 80)
    long_content = """
    This proposal outlines a comprehensive strategy for improving our DAO's treasury management and governance processes. 
    
    We propose to implement the following changes:
    
    1. Establish a dedicated treasury committee with rotating members selected through a fair voting process
    2. Create quarterly reports on treasury performance and asset allocation strategies
    3. Implement automated stacking mechanisms to maximize returns on our STX holdings
    4. Develop partnerships with other DAOs for collaborative investment opportunities
    5. Create a reserve fund for emergency situations and unexpected market downturns
    
    The implementation timeline spans 6 months with regular checkpoints and community feedback sessions.
    
    Expected benefits include:
    - Improved transparency in treasury operations
    - Better risk management through diversification
    - Increased returns through strategic stacking
    - Enhanced community engagement in financial decisions
    
    --- Metadata ---
    Proposal Type: Treasury Management
    Category: Governance
    Impact Level: High
    """
    tester.run_full_flow_test(long_content, proposal_passed=True)
    
    print("\n" * 2)
    
    # Test 3: Failed proposal
    print("TEST 3: Failed Proposal")
    print("=" * 80)
    failed_content = "Let's spend all our treasury on a risky investment scheme that promises 1000% returns!"
    tester.run_full_flow_test(failed_content, proposal_passed=False)


if __name__ == "__main__":
    main() 