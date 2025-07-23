"""Example script demonstrating how to use the STX Transfer Task.

This script shows how to create queue messages that will be processed
by the STX Transfer Task to send STX tokens to recipients.
"""

from uuid import UUID

from app.backend.factory import backend
from app.backend.models import QueueMessageCreate, QueueMessageType


def create_stx_transfer_message(
    wallet_id: UUID = None,
    recipient: str = None,
    amount: int = None,
    fee: int = 200,
    memo: str = "",
    dao_id: UUID = None,
) -> str:
    """Create a queue message for STX transfer.

    Args:
        wallet_id: UUID of the wallet to send STX from (None = use backend wallet)
        recipient: STX address to send tokens to (e.g., "SP1ABC...DEF")
        amount: Amount of STX to send (in STX, not microSTX)
        fee: Transaction fee in microSTX (default: 200)
        memo: Optional memo for the transaction
        dao_id: Optional DAO ID if this transfer is DAO-related

    Returns:
        str: ID of the created queue message

    Examples:
        # Send 5 STX from a specific wallet
        message_id = create_stx_transfer_message(
            wallet_id=UUID("12345678-1234-1234-1234-123456789abc"),
            recipient="SP1ABC123DEF456GHI789JKL012MNO345PQR678",
            amount=5,
            fee=250,
            memo="Payment for services"
        )

        # Send 1 STX from backend wallet (for system funding)
        message_id = create_stx_transfer_message(
            wallet_id=None,  # Use backend wallet
            recipient="SP1ABC123DEF456GHI789JKL012MNO345PQR678",
            amount=1,
            memo="Agent account funding"
        )
    """
    # Create the queue message
    queue_message = QueueMessageCreate(
        type=QueueMessageType.get_or_create("stx_transfer"),
        wallet_id=wallet_id,
        dao_id=dao_id,
        message={
            "recipient": recipient,
            "amount": amount,
            "fee": fee,
            "memo": memo,
        },
    )

    # Save to the queue
    created_message = backend.create_queue_message(queue_message)
    return str(created_message.id)


def create_multiple_stx_transfers(transfers: list) -> list:
    """Create multiple STX transfer messages at once.

    Args:
        transfers: List of dictionaries with transfer parameters

    Returns:
        list: List of created message IDs

    Example:
        transfers = [
            {
                "wallet_id": UUID("12345678-1234-1234-1234-123456789abc"),
                "recipient": "SP1ABC123DEF456GHI789JKL012MNO345PQR678",
                "amount": 10,
                "memo": "Payment 1"
            },
            {
                "wallet_id": UUID("87654321-4321-4321-4321-cba987654321"),
                "recipient": "SP2DEF456GHI789JKL012MNO345PQR678STU",
                "amount": 5,
                "memo": "Payment 2"
            }
        ]
        message_ids = create_multiple_stx_transfers(transfers)
    """
    message_ids = []

    for transfer in transfers:
        message_id = create_stx_transfer_message(
            wallet_id=transfer["wallet_id"],
            recipient=transfer["recipient"],
            amount=transfer["amount"],
            fee=transfer.get("fee", 200),
            memo=transfer.get("memo", ""),
            dao_id=transfer.get("dao_id"),
        )
        message_ids.append(message_id)

    return message_ids


# Example usage
if __name__ == "__main__":
    # Example wallet and recipient (replace with real values)
    example_wallet_id = UUID("12345678-1234-1234-1234-123456789abc")
    example_recipient = "SP1ABC123DEF456GHI789JKL012MNO345PQR678STU"

    print("Creating STX transfer queue message...")

    try:
        # Create a single transfer message
        message_id = create_stx_transfer_message(
            wallet_id=example_wallet_id,
            recipient=example_recipient,
            amount=1,  # Send 1 STX
            fee=200,  # 200 microSTX fee
            memo="Test transfer from example script",
        )

        print(f"Successfully created STX transfer message: {message_id}")
        print(
            f"The STX Transfer Task will process this message and send 1 STX "
            f"from wallet {example_wallet_id} to {example_recipient}"
        )

    except Exception as e:
        print(f"Error creating STX transfer message: {e}")

    # Example of multiple transfers
    print("\nExample of multiple transfers:")
    example_transfers = [
        {
            "wallet_id": example_wallet_id,
            "recipient": "SP1ABC123DEF456GHI789JKL012MNO345PQR678STU",
            "amount": 2,
            "memo": "Payment to Alice",
        },
        {
            "wallet_id": example_wallet_id,
            "recipient": "SP2DEF456GHI789JKL012MNO345PQR678STUVW",
            "amount": 3,
            "memo": "Payment to Bob",
        },
    ]

    try:
        message_ids = create_multiple_stx_transfers(example_transfers)
        print(f"Created {len(message_ids)} transfer messages: {message_ids}")
    except Exception as e:
        print(f"Error creating multiple transfers: {e}")
