#!/usr/bin/env python3
"""
Grok-4 live X search via OpenRouter
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------
# USER INFO
# --------------------------------------------------------------
USERNAME     = "biwas_"
CURRENT_TIME = "November 11, 2025 01:21 PM +0545"
COUNTRY      = "NP"

# --------------------------------------------------------------
# OPENROUTER CONFIG
# --------------------------------------------------------------
API_KEY   = os.getenv("AIBTC_CHAT_API_KEY")
MODEL     = os.getenv("AIBTC_CHAT_DEFAULT_MODEL", "x-ai/grok-4")
BASE_URL  = "https://openrouter.ai/api/v1"
REFERER   = os.getenv("OPENROUTER_REFERER", "https://aibtc.com")
TITLE     = os.getenv("OPENROUTER_TITLE", "AIBTC Dev Tool")

# --------------------------------------------------------------
# NATIVE GROK TOOLS
# --------------------------------------------------------------
x_ai_tools = [
    {"type": "web_search"},
    {"type": "x_search"}
]

# --------------------------------------------------------------
# MESSAGES
# --------------------------------------------------------------
messages = [
    {
        "role": "system",
        "content": (
            f"You are a concise X-search assistant. Current time: {CURRENT_TIME}, country: {COUNTRY}. "
            "Use the `x_search` tool with query `from:{USERNAME} since:2025-09-01` (mode='Latest') "
            "and `web_search` only if needed. Return ONLY the final answer:\n"
            "- Profile line: @handle (followers, bio if any)\n"
            "- One line per recent post, newest first.\n"
            "No markdown, no tables, no extra text."
        )
    },
    {
        "role": "user",
        "content": f"Search X for @{USERNAME} profile and recent posts."
    }
]

# --------------------------------------------------------------
# HELPER: Pretty print JSON
# --------------------------------------------------------------
def pp(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))

# --------------------------------------------------------------
# CALL OPENROUTER
# --------------------------------------------------------------
def call_openrouter(messages, tools=None):
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
    }
    if tools:
        payload["tools"] = tools

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": REFERER,
        "X-Title": TITLE,
        "Content-Type": "application/json"
    }

    print("\n" + "="*60)
    print("REQUEST PAYLOAD:")
    print("="*60)
    pp(payload)

    resp = httpx.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    print("\n" + "="*60)
    print("RESPONSE FROM OPENROUTER:")
    print("="*60)
    pp(data)

    return data

# --------------------------------------------------------------
# MAIN TOOL LOOP WITH FULL DEBUG
# --------------------------------------------------------------
print(f"Starting X profile search for @{USERNAME}...\n")

data = call_openrouter(messages, x_ai_tools)
choice = data["choices"][0]
msg = choice["message"]

iteration = 1

while "tool_calls" in msg:
    print(f"\n{'-'*60}")
    print(f"ITERATION {iteration}: TOOL CALL DETECTED")
    print(f"{'-'*60}")

    # Append assistant's message with tool calls
    messages.append(msg)

    # Print each tool call
    for i, tc in enumerate(msg["tool_calls"]):
        print(f"\nTool Call {i+1}:")
        print(f"  Function: {tc['function']['name']}")
        print(f"  Arguments:")
        args = json.loads(tc["function"]["arguments"])
        pp(args)

    print(f"\nSending updated messages back to model (with tool calls)...")
    data = call_openrouter(messages, x_ai_tools)
    choice = data["choices"][0]
    msg = choice["message"]

    # Check if tool results came back
    if "tool_responses" in data:
        print(f"\nTOOL RESPONSES RECEIVED:")
        for tr in data["tool_responses"]:
            print(f"\nTool: {tr['name']}")
            content = tr.get("content", "")
            if isinstance(content, list):
                for item in content:
                    print(f"  - {item}")
            else:
                print(f"  {content}")

    # Append tool response messages if present
    if "tool_responses" in data:
        for tr in data["tool_responses"]:
            messages.append({
                "role": "tool",
                "name": tr["name"],
                "content": json.dumps(tr["content"]) if isinstance(tr["content"], (dict, list)) else str(tr["content"])
            })

    iteration += 1

# --------------------------------------------------------------
# FINAL OUTPUT
# --------------------------------------------------------------
print("\n" + "="*60)
print("FINAL CONVERSATION MESSAGES:")
print("="*60)
for m in messages:
    role = m["role"].upper()
    content = m["content"][:200] + "..." if len(m.get("content", "")) > 200 else m.get("content", "")
    print(f"[{role}] {content}")
    if "tool_calls" in m:
        for tc in m["tool_calls"]:
            print(f"   → Tool: {tc['function']['name']} | Args: {tc['function']['arguments']}")

print("\n" + "="*60)
print("FINAL ANSWER FROM MODEL:")
print("="*60)
final_answer = msg["content"].strip()
print(final_answer)

print("\n" + "="*60)
print("DONE")
print("="*60)