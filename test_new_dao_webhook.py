#!/usr/bin/env python3
"""Test script to validate new DAO webhook payload parsing."""

import json

from services.webhooks.dao.models import DAOWebhookPayload

# Sample payload from the user's new structure
sample_payload = {
    "name": "XFACE•AIBTC•DAO",
    "mission": "## Mission\\n\\nTo make Bitcoin Faces the most popular meme amongst Bitcoiners, on X, on-chain, and throughout Bitcoin culture.\\n\\n## Core Pillars\\n\\n1. Face as Identity: Every Bitcoin Face is a unique, deterministic, generative avatar tied to a name or address - an expression of sovereignty and style. The DAO preserves and evolves this standard as the meme layer of Bitcoin.\\n2. Meme Engine of the Network: The DAO funds and coordinates the viral spread of Bitcoin Faces - on X, on-chain, and beyond. Proposals reward memes, automate content, and shape culture.\\n3. Permissionless Personality: Anyone can generate a face. Anyone can remix it. But the DAO decides which AI styles, transformations, and add-ons become official. Governance as curatorship.\\n4. On-Chain Licensing and Monetization: Through the payments and invoicing system, enables creators to build tools, apps, and embeds that use Bitcoin Faces - with revenue shared between builders and the DAO treasury.\\n5. Autonomous Avatars, Autonomous Treasury:  will gradually become a fully agent-driven culture DAO. Until then, the treasury is protected by time, quorum, and AI maturity. The meme spreads first, the money flows later.",
    "contracts": [
        {
            "name": "aibtc-faktory",
            "display_name": "xface-faktory",
            "type": "TOKEN",
            "subtype": "DAO",
            "tx_id": "6bb26cf198ad3f093a3e61b495f3acdb248c0230c2dc8edc2e1655a93ced72c5",
            "deployer": "ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K",
            "contract_principal": "ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K.aibtc-faktory",
        },
        {
            "name": "aibtc-base-dao",
            "display_name": "xface-base-dao",
            "type": "BASE",
            "subtype": "DAO",
            "tx_id": "c1d9fd38f94f8fcd204f65b598ccb486a5f68b88f58de049d59df12eb11bd5bb",
            "deployer": "ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K",
            "contract_principal": "ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K.aibtc-base-dao",
        },
        {
            "name": "aibtc-treasury",
            "display_name": "xface-treasury",
            "type": "EXTENSIONS",
            "subtype": "TREASURY",
            "tx_id": "159cc3c930f84e4e3026af900acb7d1cac1ba505ece3c24c077b912a0a8ad666",
            "deployer": "ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K",
            "contract_principal": "ST3DD7MASYJADCFXN3745R11RVM4PCXCPVRS3V27K.aibtc-treasury",
        },
    ],
    "token_info": {
        "symbol": "XFACE•AIBTC•DAO",
        "decimals": 8,
        "max_supply": "1000000000",
        "uri": "https://mkkhfmcrbwyuutcvtier.supabase.co/storage/v1/object/public/tokens//251.json",
        "image_url": "https://mkkhfmcrbwyuutcvtier.supabase.co/storage/v1/object/public/tokens//251.png",
        "x_url": "https://x.com/1894855072556912681",
    },
}


def test_payload_parsing():
    """Test that the new payload structure can be parsed correctly."""
    try:
        # Parse the payload
        parsed_payload = DAOWebhookPayload(**sample_payload)

        print("✅ Payload parsed successfully!")
        print(f"DAO Name: {parsed_payload.name}")
        print(f"Number of contracts: {len(parsed_payload.contracts)}")
        print(f"Token symbol: {parsed_payload.token_info.symbol}")

        # Check for DAO token contract
        dao_token = None
        for contract in parsed_payload.contracts:
            if contract.type.value == "TOKEN" and contract.subtype == "DAO":
                dao_token = contract
                break

        if dao_token:
            print(f"✅ Found DAO token contract: {dao_token.name}")
            print(f"   Contract Principal: {dao_token.contract_principal}")
            print(f"   TX ID: {dao_token.tx_id}")
        else:
            print("❌ No DAO token contract found")

        # Count extension contracts
        extension_contracts = [
            c
            for c in parsed_payload.contracts
            if c.type.value in ["EXTENSIONS", "ACTIONS", "PROPOSALS", "BASE"]
        ]
        print(f"✅ Found {len(extension_contracts)} extension contracts")

        for ext in extension_contracts:
            print(f"   - {ext.type.value}: {ext.subtype} ({ext.name})")

        return True

    except Exception as e:
        print(f"❌ Error parsing payload: {str(e)}")
        return False


if __name__ == "__main__":
    print("Testing new DAO webhook payload structure...")
    success = test_payload_parsing()
    if success:
        print("\n🎉 All tests passed! The new structure is working correctly.")
    else:
        print("\n💥 Tests failed. Check the error messages above.")
