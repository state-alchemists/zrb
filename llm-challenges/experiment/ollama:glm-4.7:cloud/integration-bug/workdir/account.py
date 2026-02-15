import asyncio
from database import Database

db = Database()

async def transfer(from_user, to_user, amount):
    """
    Transfers money between users using atomic database operations
    to prevent race conditions and ensure no money is lost.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")

    success = await db.atomic_transfer(from_user, to_user, amount)

    if not success:
        print(f"Insufficient funds for {from_user}")
        return False

    print(f"Transfer complete: {from_user} -> {to_user}")
    return True
