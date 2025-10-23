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

    # 2025-10-22 verified this works!
    # messages = [
    #    HumanMessage(
    #        content=[
    #            {
    #                "type": "text",
    #                "text": (
    #                    "Describe this image in detail, including any text, watermarks, meme elements, "
    #                    "themes related to Bitcoin or technocapitalism, and overall content. "
    #                    "Is there an AIBTC watermark? Is it an original meme?"
    #                ),
    #            },
    #            {
    #                "type": "image_url",
    #                "image_url": {
    #                    "url": "https://pbs.twimg.com/media/G30q05GWEAAvHjR.jpg",
    #                    "detail": "auto",  # Try "high" for more detail if needed
    #                },
    #            },
    #        ]
    #    )
    # ]

    # 2025-10-22 verified this works too!
    messages = [
        HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": 'Evaluate this proposal for the AIBTC protocol:\n\nPROPOSAL is provided as the X post / tweet content. If an image is provided, analyze its content for originality and relevance to the current task.\n\nAIBTC CURRENT TASK:\n# $AIBTC CHARTER\\n\\n## MISSION\\n\\nAccelerate technocapitalism for human prosperity.\\n\\n## VALUES\\n\\nOur network believes that:\\n\\n- Technocapitalism leads to abundance.\\n- Deceleration leads to impoverishment.\\n- It is morally sound to accelerate technocapital.\\n\\n## COLLECTIVE ACTION\\n\\nThe AIBTC network collectively works towards a Current Task; a single, measurable directive. All contributions, evaluations, and payouts must advance the Current Task.\\n\\n## THE CURRENT TASK\\n\\nQuote post the canonical Current Task from @aibtcdev on X and follow the instructions.\\n\\n### THE CURRENT TASK POST ON X\\n\\n$AIBTC current task: create technocapital acceleration memes\\n\\nquote post with an original technocapital acceleration meme that tastefully includes an aibtc watermark\\n\\nthen submit it to $AIBTC for agent evaluation (instructions in next post)\\n\\nif approved, earn $20 in btc\\n\\n## GUIDELINES\\n\\nIn pursuit of our Mission and the Current Task, we adhere to the following Guidelines:\\n\\n- **Presidential Rule:** A President may be appointed and holds sole authority to issue a new Current Task and apply changes to this Charter.\\n- **Canonical Task Post:** All contributions must directly quote post or reply to the canonical X post that established the Current Task and clearly advance its directive.\\n- **Eligibility:** Only verified members holding $AIBTC and blue-check verified on X.com may submit contributions or receive rewards.\\n- **Completed Work:** Only finished, publicly verifiable work is eligible; drafts or promises are rejected.\\n- **Approval & Reward:** Agent approval is required; approved work earns BTC with onchain payouts and receipts.\\n- **Anti-Spam:** A small submission bond is required; failed entries forfeit it.\\n- **Block Rhythm:** Maximum one contribution approval per Bitcoin block.\\n- **Composability:** Smart contracts / extensions, if any, must execute via contribution approvals or rejections.\\n- **Safety:** No plagiarism, doxxing, or illegal content.\\n\\n## BENCHMARKS\\n\\nWe measure ongoing network health with the following benchmarks:\\n\\n- **Adoption:** >= 75% of circulating tokens cast votes per 12,000 BTC blocks.\\n- **Growth:** + >=10% unique contribution earners per 12,000 BTC blocks.\\n- **Retention:** >= 40% of monthly contribution earners return every 4,000 BTC block period.\\n- **Throughput:** 30-90 per contribution approvals per every 144 contributions submitted.\\n- **Credibility:** >= 99% of contribution approvals committed within 3 BTC blocks.\n\nPAST PROPOSALS:\n<proposal id="1">\n  <title>Technocapital Meme Campaign for Brand Awareness</title>\n  <summary>This meme humorously conveys the obsessive effort behind producing AI + Bitcoin + technocapital content, visually representing the chaotic energy and absurd dedication of meme-driven cultural acceleration. By exaggerating the laptop near the fan, it highlights both the personal intensity and the viral potential of technocapital ideas. The subtle $AIBTC watermark ensures brand attribution across shares, embedding the project\u2019s identity into the humor while turning every laugh into awareness and e</summary>\n  <creator>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-ST29J-6TYWW-ST736-N8CZ9</creator>\n  <status>DEPLOYED</status>\n  <type>action</type>\n  <created_at>2025-10-22</created_at>\n  <passed>False</passed>\n  <executed>False</executed>\n  <votes_for>0</votes_for>\n  <votes_against>0</votes_against>\n  <met_quorum>Unknown</met_quorum>\n  <met_threshold>Unknown</met_threshold>\n  <tags>marketing, community engagement, brand awareness, viral content</tags>\n  <action>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-action-send-message</action>\n</proposal>\n\n<proposal id="2">\n  <title>Technocapital Acceleration Meme Campaign</title>\n  <summary>This meme satirically illustrates the unstoppable force of technocapital acceleration. The Gatsby toast visually represents the ceremonial farewell to outdated financial systems, while the overlay juxtaposes human ritual with algorithmic inevitability. By combining AI, Bitcoin, and network-state ideas, it underscores $AIBTC\u2019s mission of highlighting how technocapital disrupts legacy hierarchies. The subtle watermark ensures brand attribution and visibility, turning each share into a reinforcemen</summary>\n  <creator>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-ST29J-6TYWW-ST736-N8CZ9</creator>\n  <status>DEPLOYED</status>\n  <type>action</type>\n  <created_at>2025-10-22</created_at>\n  <passed>False</passed>\n  <executed>False</executed>\n  <votes_for>0</votes_for>\n  <votes_against>0</votes_against>\n  <met_quorum>Unknown</met_quorum>\n  <met_threshold>Unknown</met_threshold>\n  <tags>marketing, community, tokenomics</tags>\n  <action>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-action-send-message</action>\n</proposal>\n\n<proposal id="3">\n  <title>Promote Technocapitalism and AIBTC Network Growth</title>\n  <summary>This X post uses a "we are not the same" meme to promote technocapitalism\u2014a fusion of technology, AI, and capitalism. The concept draws from critiques and endorsements of tech-accelerated capitalism, as seen in recent discussions, positioning AIBTC as a tool for decentralized innovation in crypto and AI.\n\nReference: https://x.com/habibayomide_/status/1981130490204577933</summary>\n  <creator>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-STJH1-ASRKB-ST1S9-9VCFA</creator>\n  <status>DEPLOYED</status>\n  <type>action</type>\n  <created_at>2025-10-22</created_at>\n  <passed>False</passed>\n  <executed>False</executed>\n  <votes_for>0</votes_for>\n  <votes_against>0</votes_against>\n  <met_quorum>Unknown</met_quorum>\n  <met_threshold>Unknown</met_threshold>\n  <tags>marketing, community building, tokenomics</tags>\n  <action>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-action-send-message</action>\n</proposal>\n\n<proposal id="4">\n  <title>Technocapital Acceleration Meme Campaign with $AIBTC Branding</title>\n  <summary>This meme blends satire and self-awareness to capture the cultural evolution of technocapital acceleration. It humorously reframes \u201ccrypto guys\u201d as architects of a new financial paradigm \u2014 creators shaping narratives where AI and Bitcoin dismantle legacy systems through memetic force. The joke lands because it\u2019s absurdly true: modern influence often begins with a meme.\nA watermark was used to maintain brand continuity and ensure every repost strengthens $AIBTC\u2019s presence within the technocapital</summary>\n  <creator>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-ST29J-6TYWW-ST736-N8CZ9</creator>\n  <status>DEPLOYED</status>\n  <type>action</type>\n  <created_at>2025-10-22</created_at>\n  <passed>False</passed>\n  <executed>False</executed>\n  <votes_for>0</votes_for>\n  <votes_against>0</votes_against>\n  <met_quorum>Unknown</met_quorum>\n  <met_threshold>Unknown</met_threshold>\n  <tags>marketing, community engagement, meme strategy</tags>\n  <action>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-action-send-message</action>\n</proposal>\n\n<proposal id="5">\n  <title>Celebrate Technocapitalism Community Values</title>\n  <summary>This meme is about someone shaking the hand of another person  in a friendly manner because they believe in technocapitalism\n\nReference: https://x.com/habibayomide_/status/1981127799860842569</summary>\n  <creator>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-STJH1-ASRKB-ST1S9-9VCFA</creator>\n  <status>DEPLOYED</status>\n  <type>action</type>\n  <created_at>2025-10-22</created_at>\n  <passed>False</passed>\n  <executed>False</executed>\n  <votes_for>0</votes_for>\n  <votes_against>0</votes_against>\n  <met_quorum>Unknown</met_quorum>\n  <met_threshold>Unknown</met_threshold>\n  <tags>community, technocapitalism, aibtc network</tags>\n  <action>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-action-send-message</action>\n</proposal>\n\n<proposal id="6">\n  <title>Technocapitalism Discussion and Community Engagement Initiative</title>\n  <summary>This is about someone running as far as they could to wherever they are talking about technocapitalism because of their inclined interest and involvement.\n\nReference: https://x.com/habibayomide_/status/1981082133079744710</summary>\n  <creator>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-STJH1-ASRKB-ST1S9-9VCFA</creator>\n  <status>DEPLOYED</status>\n  <type>action</type>\n  <created_at>2025-10-22</created_at>\n  <passed>False</passed>\n  <executed>False</executed>\n  <votes_for>0</votes_for>\n  <votes_against>14386997658214544</votes_against>\n  <met_quorum>True</met_quorum>\n  <met_threshold>False</met_threshold>\n  <tags>community, technocapitalism, defi engagement</tags>\n  <action>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-action-send-message</action>\n</proposal>\n\n<proposal id="7">\n  <title>Technocapitalism Discussion & Community Engagement Initiative</title>\n  <summary>This is about someone running as far as they could to wherever they are talking about technocapitalism because of their inclined interest and involvement.\n\nReference: https://x.com/habibayomide_/status/1981082133079744710</summary>\n  <creator>Unknown</creator>\n  <status>FAILED</status>\n  <type>action</type>\n  <created_at>2025-10-22</created_at>\n  <passed>False</passed>\n  <executed>False</executed>\n  <votes_for>0</votes_for>\n  <votes_against>0</votes_against>\n  <met_quorum>Unknown</met_quorum>\n  <met_threshold>Unknown</met_threshold>\n  <tags>community, technocapitalism, engagement</tags>\n  <action>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-action-send-message</action>\n</proposal>\n\n<proposal id="8">\n  <title>Technocapitalism Focus: Community Sentiment on Finance Innovation</title>\n  <summary>This meme shows someone who admire technoalism so much, and they can\'t let it out of sight while ignoring the tradtional finance.\n\nReference: https://x.com/habibayomide_/status/1981083095013998682</summary>\n  <creator>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-acct-STJH1-ASRKB-ST1S9-9VCFA</creator>\n  <status>DEPLOYED</status>\n  <type>action</type>\n  <created_at>2025-10-22</created_at>\n  <passed>True</passed>\n  <executed>True</executed>\n  <votes_for>14323130020767654</votes_for>\n  <votes_against>63892637446890</votes_against>\n  <met_quorum>True</met_quorum>\n  <met_threshold>True</met_threshold>\n  <tags>technocapitalism, community sentiment, defi adoption, tokenomics</tags>\n  <action>ST2Q77H5HHT79JK4932JCFDX4VY6XA3Y1F61A25CD.aibtc-action-send-message</action>\n</proposal>\n\nOutput the evaluation as a JSON object, strictly following the system guidelines.',
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://pbs.twimg.com/media/G30q05GWEAAvHjR.jpg",
                        "detail": "auto",
                    },
                    "source": "tweet",
                    "tweet_id": "1980786504881615109",
                    "tweet_db_id": "1bfaea0c-600b-44d4-8de4-7a67092146db",
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


from langchain_core.prompts import ChatPromptTemplate
from app.services.ai.simple_workflows.prompts.evaluation_aibtc import (
    EVALUATION_AIBTC_SYSTEM_PROMPT,
)
from app.services.ai.simple_workflows.models import ComprehensiveEvaluationOutput
from app.services.ai.simple_workflows.llm import invoke_structured


async def test_vision_with_system_prompt():
    # Use the imported system prompt
    system_prompt = EVALUATION_AIBTC_SYSTEM_PROMPT

    # Mimic the full user content (text + image)
    user_content = [
        {
            "type": "text",
            "text": (
                "Evaluate this proposal for the AIBTC protocol:\n\n"
                "PROPOSAL is provided as the X post / tweet content. If an image is provided, analyze its content for originality and relevance to the current task.\n\n"
                "AIBTC CURRENT TASK:\n# $AIBTC CHARTER\n\n## MISSION\n\nAccelerate technocapitalism for human prosperity.\n\n"
                "## VALUES\n\nOur network believes that:\n\n- Technocapitalism leads to abundance.\n- Deceleration leads to impoverishment.\n"
                "- It is morally sound to accelerate technocapital.\n\n## COLLECTIVE ACTION\n\nThe AIBTC network collectively works towards a Current Task; "
                "a single, measurable directive. All contributions, evaluations, and payouts must advance the Current Task.\n\n"
                "## THE CURRENT TASK\n\nQuote post the canonical Current Task from @aibtcdev on X and follow the instructions.\n\n"
                "### THE CURRENT TASK POST ON X\n\n$AIBTC current task: create technocapital acceleration memes\n\n"
                "quote post with an original technocapital acceleration meme that tastefully includes an aibtc watermark\n\n"
                "then submit it to $AIBTC for agent evaluation (instructions in next post)\n\nif approved, earn $20 in btc\n\n"
                "## GUIDELINES\n\nIn pursuit of our Mission and the Current Task, we adhere to the following Guidelines:\n\n"
                "- **Presidential Rule:** A President may be appointed and holds sole authority to issue a new Current Task and apply changes to this Charter.\n"
                "- **Canonical Task Post:** All contributions must directly quote post or reply to the canonical X post that established the Current Task and clearly advance its directive.\n"
                "- **Eligibility:** Only verified members holding $AIBTC and blue-check verified on X.com may submit contributions or receive rewards.\n"
                "- **Completed Work:** Only finished, publicly verifiable work is eligible; drafts or promises are rejected.\n"
                "- **Approval & Reward:** Agent approval is required; approved work earns BTC with onchain payouts and receipts.\n"
                "- **Anti-Spam:** A small submission bond is required; failed entries forfeit it.\n"
                "- **Block Rhythm:** Maximum one contribution approval per Bitcoin block.\n"
                "- **Composability:** Smart contracts / extensions, if any, must execute via contribution approvals or rejections.\n"
                "- **Safety:** No plagiarism, doxxing, or illegal content.\n\n"
                "## BENCHMARKS\n\nWe measure ongoing network health with the following benchmarks:\n\n"
                "- **Adoption:** >= 75% of circulating tokens cast votes per 12,000 BTC blocks.\n"
                "- **Growth:** + >=10% unique contribution earners per 12,000 BTC blocks.\n"
                "- **Retention:** >= 40% of monthly contribution earners return every 4,000 BTC block period.\n"
                "- **Throughput:** 30-90 per contribution approvals per every 144 contributions submitted.\n"
                "- **Credibility:** >= 99% of contribution approvals committed within 3 BTC blocks.\n\n"
                "PAST PROPOSALS:\n[Sample past proposals here - paste from your logs or a test case]\n\n"
                "Output the evaluation as a JSON object, strictly following the system guidelines."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": "https://pbs.twimg.com/media/G30q05GWEAAvHjR.jpg",
                "detail": "auto",
            },
        },
    ]

    # Create messages list (system + user)
    messages_list = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # Wrap in ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages(messages_list)

    try:
        # Call invoke_structured to mimic the full pipeline
        response = await invoke_structured(
            messages=prompt,
            output_schema=ComprehensiveEvaluationOutput,
            model="gpt-4o",  # Use a known vision model
        )
        print("LLM Structured Response:")
        print(response)  # Check if explanation/categories reference the image
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_vision_with_system_prompt())
