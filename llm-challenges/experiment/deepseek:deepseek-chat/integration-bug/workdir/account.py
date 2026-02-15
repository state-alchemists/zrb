import asyncio
from database import Database

db = Database()

async def transfer(from_user, to_user, amount):
    """
    Transfers money between users atomically.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")
    
    # Use atomic database operation
    success = await db.atomic_transfer(from_user, to_user, amount)
    
    if not success:
        print(f"Insufficient funds for {from_user}")
        return False
    
    print(f"Transfer complete: {from_user} -> {to_user}")
    return True
