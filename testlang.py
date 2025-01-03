import asyncio
import datetime
import uuid
from backend.factory import backend
from backend.models import Profile
from services.langgraph import execute_langgraph_stream

# -----------------------------------------------------
# Example usage
# -----------------------------------------------------

if __name__ == "__main__":

    async def main():
        # Example profile
        profile = Profile(
            account_index="0",
            id="419781f6-c250-4bd6-be9e-fb347d1f77f9",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )
        # Example history
        history = [
            {
                "role": "assistant",
                "content": "Sure, what exactly would you like to know?",
            },
        ]

        # Example persona
        # generate persona from supabase information
        agent = backend.get_agent(
            agent_id=uuid.UUID("daac3d13-bfba-4927-8cb0-852c2988f176")
        )
        task = backend.get_task(
            task_id=uuid.UUID("9309642a-2026-4613-b079-7aee6cc2ef03")
        )
        persona = (
            "You are a helpful financial assistant with a light-hearted tone. "
            "You have a positive attitude and a sense of humor. "
            f"Your name is {agent.name}. "
            f"Backstory: {agent.backstory}. Role: {agent.role}. Goal: {agent.goal}. "
        )
        print(task.prompt)
        # Prepare the async generator
        stream_generator = execute_langgraph_stream(
            profile=profile,
            history=history,
            input_str=task.prompt,
            persona=persona,
        )

        # Collect streaming output
        async for event in stream_generator:
            if event["type"] == "token":
                # Print tokens as they are generated
                print(event["content"], end="", flush=True)
            elif event["type"] == "end":
                print("\n--- LLM finished sending tokens ---")
            elif event["type"] == "tool_execution":
                # Intermediate step from a tool
                print(f"\n[TOOL] {event}")
            elif event["type"] == "result":
                print("\nFinal LLM Response:", event["content"])

    # Run the async function in an event loop
    asyncio.run(main())
