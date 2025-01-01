import asyncio
import os
from datetime import datetime
from db.client import services_client
from dotenv import load_dotenv
from lib.models import TwitterResponse
from typing import Dict, List, Optional

# Load environment variables
load_dotenv()


def test_conversation_endpoints():
    """Test conversation-related endpoints."""
    print("\nTesting Conversation Endpoints:")
    test_address = "test_address"

    # Test get_conversations
    conversations = services_client.database.get_conversations(test_address)
    print(f"Get Conversations: {len(conversations)} conversations found")

    # Test get_latest_conversation
    latest = services_client.database.get_latest_conversation(test_address)
    print(f"Get Latest Conversation: {'Found' if latest else 'Not found'}")

    if latest:
        # Test get_conversation_history
        history = services_client.database.get_conversation_history(latest["id"])
        print(f"Get Conversation History: {len(history)} messages found")


def test_crew_endpoints():
    """Test crew-related endpoints."""
    print("\nTesting Crew Endpoints:")
    test_address = "test_address"

    # Test get_public_crews
    crews = services_client.database.get_public_crews()
    print(f"Get Public Crews: {len(crews.crews) if crews.crews else 0} crews found")

    # Create a test crew
    crew_data = {
        "name": "Test Crew",
        "description": "Test crew for endpoint testing",
        "creator_email": "test@example.com",
    }
    created_crew = services_client.database.create_crew(crew_data)
    print(f"Create Crew: {'Success' if created_crew.crew else 'Failed'}")

    if created_crew.crew:
        crew_id = created_crew.crew.id

        # Test get_crew
        crew = services_client.database.get_crew(crew_id)
        print(f"Get Crew: {'Found' if crew.crew else 'Not found'}")

        # Test update_crew
        updates = {"description": "Updated description"}
        updated = services_client.database.update_crew(crew_id, updates)
        print(f"Update Crew: {'Success' if updated.crew else 'Failed'}")

        # Test crew executions
        executions = services_client.database.get_crew_executions(test_address)
        print(
            f"Get Crew Executions: {len(executions.executions) if executions.executions else 0} executions found"
        )

        # Test delete_crew
        deleted = services_client.database.delete_crew(crew_id)
        print(f"Delete Crew: {'Success' if deleted.success else 'Failed'}")


def test_agent_endpoints():
    """Test agent-related endpoints."""
    print("\nTesting Agent Endpoints:")
    test_crew_id = 1

    # Test get_crew_agents
    agents = services_client.database.get_crew_agents(test_crew_id)
    print(f"Get Crew Agents: {len(agents.agents) if agents.agents else 0} agents found")

    # Create a test agent
    agent_data = {
        "name": "Test Agent",
        "role": "Tester",
        "goal": "Test endpoints",
        "backstory": "Created for testing",
        "crew_id": test_crew_id,
    }
    created_agent = services_client.database.create_agent(agent_data)
    print(f"Create Agent: {'Success' if created_agent.agent else 'Failed'}")

    if created_agent.agent:
        agent_id = created_agent.agent.id

        # Test update_agent
        updates = {"backstory": "Updated backstory"}
        updated = services_client.database.update_agent(agent_id, updates)
        print(f"Update Agent: {'Success' if updated.agent else 'Failed'}")

        # Test delete_agent
        deleted = services_client.database.delete_agent(agent_id)
        print(f"Delete Agent: {'Success' if deleted.success else 'Failed'}")


def test_profile_endpoints():
    """Test profile-related endpoints."""
    print("\nTesting Profile Endpoints:")
    test_address = "test_address"

    # Test get_user_profile
    profile = services_client.database.get_user_profile(test_address)
    print(f"Get User Profile: {'Found' if profile.profile else 'Not found'}")

    # Test get_user_role
    role = services_client.database.get_user_role(test_address)
    print(f"Get User Role: {role.role if role.role else 'Not found'}")

    # Create a test profile
    profile_data = {
        "stx_address": test_address,
        "user_role": "tester",
        "account_index": 0,
    }
    created_profile = services_client.database.create_user_profile(profile_data)
    print(f"Create User Profile: {'Success' if created_profile.profile else 'Failed'}")

    if created_profile.profile:
        # Test update_user_profile
        updates = {"user_role": "updated_tester"}
        updated = services_client.database.update_user_profile(test_address, updates)
        print(f"Update User Profile: {'Success' if updated.profile else 'Failed'}")

        # Test delete_user_profile
        deleted = services_client.database.delete_user_profile(test_address)
        print(f"Delete User Profile: {'Success' if deleted.success else 'Failed'}")


def test_task_endpoints():
    """Test task-related endpoints."""
    print("\nTesting Task Endpoints:")
    test_crew_id = 1
    test_agent_id = 1

    # Test get_crew_tasks
    crew_tasks = services_client.database.get_crew_tasks(test_crew_id)
    print(
        f"Get Crew Tasks: {len(crew_tasks.tasks) if crew_tasks.tasks else 0} tasks found"
    )

    # Test get_agent_tasks
    agent_tasks = services_client.database.get_agent_tasks(test_agent_id)
    print(
        f"Get Agent Tasks: {len(agent_tasks.tasks) if agent_tasks.tasks else 0} tasks found"
    )

    # Create a test task
    task_data = {
        "profile_id": "test_profile",
        "crew_id": test_crew_id,
        "agent_id": test_agent_id,
        "task_name": "Test Task",
        "task_description": "Test task description",
        "task_expected_output": "Test output",
    }
    created_task = services_client.database.create_task(task_data)
    print(f"Create Task: {'Success' if created_task.task else 'Failed'}")

    if created_task.task:
        task_id = created_task.task.id

        # Test get_task
        task = services_client.database.get_task(task_id)
        print(f"Get Task: {'Found' if task.task else 'Not found'}")

        # Test update_task
        updates = {"task_description": "Updated description"}
        updated = services_client.database.update_task(task_id, updates)
        print(f"Update Task: {'Success' if updated.task else 'Failed'}")

        # Test delete_task
        deleted = services_client.database.delete_task(task_id)
        print(f"Delete Task: {'Success' if deleted.success else 'Failed'}")

    # Test delete_agent_tasks
    deleted_all = services_client.database.delete_agent_tasks(test_agent_id)
    print(f"Delete Agent Tasks: {'Success' if deleted_all.success else 'Failed'}")


def test_cron_endpoints():
    """Test cron-related endpoints."""
    print("\nTesting Cron Endpoints:")
    test_crew_id = 1

    # Test get_enabled_crons
    enabled_crons = services_client.database.get_enabled_crons()
    print(
        f"Get Enabled Crons: {len(enabled_crons.crons) if enabled_crons.crons else 0} crons found"
    )

    # Test get_enabled_crons_detailed
    detailed_crons = services_client.database.get_enabled_crons_detailed()
    print(
        f"Get Detailed Crons: {len(detailed_crons.crons) if detailed_crons.crons else 0} crons found"
    )

    # Test get_crew_crons
    crew_crons = services_client.database.get_crew_crons(test_crew_id)
    print(
        f"Get Crew Crons: {len(crew_crons.crons) if crew_crons.crons else 0} crons found"
    )

    # Create a test cron
    cron_data = {
        "profile_id": "test_profile",
        "crew_id": test_crew_id,
        "AIBTC_CRON_ENABLED": True,
        "cron_interval": "0 * * * *",
        "cron_input": "Test input",
    }
    created_cron = services_client.database.create_cron(cron_data)
    print(f"Create Cron: {'Success' if created_cron.cron else 'Failed'}")

    if created_cron.cron:
        cron_id = created_cron.cron.id

        # Test update_cron_input
        updated = services_client.database.update_cron_input(cron_id, "Updated input")
        print(f"Update Cron Input: {'Success' if updated.cron else 'Failed'}")

        # Test toggle_cron
        toggled = services_client.database.toggle_cron(cron_id, False)
        print(f"Toggle Cron: {'Success' if toggled.cron else 'Failed'}")


def test_twitter_endpoints():
    """Test Twitter-related endpoints."""
    print("\nTesting Twitter Endpoints:")
    test_author_id = "test_author"
    test_tweet_id = "test_tweet"
    test_thread_id = 1

    # Test author endpoints
    try:
        author = services_client.database.get_author(test_author_id)
        print(f"Get Author: {'Found' if author.author else 'Not found'}")
    except Exception as e:
        print(f"Get Author failed: {str(e)}")
        author = TwitterResponse(success=True, author=None)

    try:
        created_author = services_client.database.create_author(
            test_author_id, "Test User", "testuser"
        )
        print(f"Create Author: {'Success' if created_author.author else 'Failed'}")
    except Exception as e:
        print(f"Create Author failed: {str(e)}")
        created_author = TwitterResponse(success=False, error=str(e))

    # Test tweet endpoints
    try:
        tweet = services_client.database.get_tweet(test_tweet_id)
        print(f"Get Tweet: {'Found' if tweet.tweet else 'Not found'}")
    except Exception as e:
        print(f"Get Tweet failed: {str(e)}")
        tweet = TwitterResponse(success=True, tweet=None)

    try:
        thread_tweets = services_client.database.get_thread_tweets(test_thread_id)
        print(
            f"Get Thread Tweets: {len(thread_tweets.tweets) if thread_tweets.tweets else 0} tweets found"
        )
    except Exception as e:
        print(f"Get Thread Tweets failed: {str(e)}")
        thread_tweets = TwitterResponse(success=True, tweets=[])

    try:
        author_tweets = services_client.database.get_author_tweets(test_author_id)
        print(
            f"Get Author Tweets: {len(author_tweets.tweets) if author_tweets.tweets else 0} tweets found"
        )
    except Exception as e:
        print(f"Get Author Tweets failed: {str(e)}")
        author_tweets = TwitterResponse(success=True, tweets=[])

    try:
        created_tweet = services_client.database.add_tweet(
            test_author_id, test_tweet_id, "Test tweet body", test_thread_id
        )
        print(f"Create Tweet: {'Success' if created_tweet.tweet else 'Failed'}")
    except Exception as e:
        print(f"Create Tweet failed: {str(e)}")
        created_tweet = TwitterResponse(success=False, error=str(e))

    # Test log endpoints
    try:
        logs = services_client.database.get_tweet_logs(test_tweet_id)
        print(f"Get Tweet Logs: {len(logs.logs) if logs.logs else 0} logs found")
    except Exception as e:
        print(f"Get Tweet Logs failed: {str(e)}")
        logs = TwitterResponse(success=True, logs=[])

    try:
        created_log = services_client.database.add_tweet_log(
            test_tweet_id, "test_status", "Test log message"
        )
        print(f"Create Tweet Log: {'Success' if created_log.log else 'Failed'}")
    except Exception as e:
        print(f"Create Tweet Log failed: {str(e)}")
        created_log = TwitterResponse(success=False, error=str(e))


def test_image_endpoints():
    """Test image-related endpoints."""
    print("\nTesting Image Endpoints:")

    # Test generate_image
    generated = services_client.image.generate_image(
        "Test prompt", size="1024x1024", n=1
    )
    print(f"Generate Image: {'Success' if generated.image_key else 'Failed'}")

    if generated.image_key:
        # Test get_image
        image_url = services_client.image.get_image(generated.image_key)
        print(f"Get Image: {'Success' if image_url else 'Failed'}")

    # Test list_images
    images = services_client.image.list_images(limit=10)
    print(f"List Images: {len(images.images) if images.images else 0} images found")


def main():
    """Run all tests."""
    print("Starting Services Client Tests")
    print("=" * 50)

    # test_conversation_endpoints()
    # test_crew_endpoints()
    # test_agent_endpoints()
    # test_profile_endpoints()
    # test_task_endpoints()
    # test_cron_endpoints()
    test_twitter_endpoints()
    # test_image_endpoints()

    print("\nTests completed!")


if __name__ == "__main__":
    main()
