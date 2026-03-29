import asyncio
from database import Database

db = Database()

async def transfer(from_user, to_user, amount):
    """
    Transfers money between users.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")
    success = await db.transfer(from_user, to_user, amount)
    if success:
        print(f"Transfer complete: {from_user} -> {to_user}")
    else:
        print(f"Transfer failed: insufficient funds for {from_user}")
    return success
