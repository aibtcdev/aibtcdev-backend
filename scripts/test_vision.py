#!/usr/bin/env python3
"""Standalone script to test LLM vision capabilities with a specific image URL."""

import asyncio
import os
import sys

# Add the parent directory (root) to the path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai.simple_workflows.llm import create_chat_openai
from langchain.schema import HumanMessage


async def test_vision():
    # Use a vision-capable model (ensure this matches your config)
    model = create_chat_openai(model="gpt-4.1")

    messages = [
        HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Describe this image in detail, including any text, watermarks, meme elements, "
                        "themes related to Bitcoin or technocapitalism, and overall content. "
                        "Is there an AIBTC watermark? Is it an original meme?"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://pbs.twimg.com/media/G30q05GWEAAvHjR.jpg",
                        "detail": "auto",  # Try "high" for more detail if needed
                    },
                },
            ]
        )
    ]

    try:
        response = await model.ainvoke(messages)
        print("LLM Response:")
        print(response.content)
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_vision())
