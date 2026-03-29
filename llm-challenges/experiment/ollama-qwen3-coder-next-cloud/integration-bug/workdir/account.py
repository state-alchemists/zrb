import asyncio
from database import Database

db = Database()

# Lock to ensure atomic transfers (prevents race conditions)
_transfer_lock = asyncio.Lock()

async def transfer(from_user, to_user, amount):
    """
    Transfers money between users atomically.
    Uses a lock to prevent race conditions during concurrent transfers.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")
    
    # Use lock to make the entire transfer operation atomic
    async with _transfer_lock:
        # Check balance
        from_balance = await db.get_balance(from_user)
        if from_balance < amount:
            print(f"Insufficient funds for {from_user}")
            return False

        # Get destination balance
        to_balance = await db.get_balance(to_user)

        # Perform transfer (now atomic - no other transfers can interleave)
        await db.set_balance(from_user, from_balance - amount)
        await db.set_balance(to_user, to_balance + amount)
    
    print(f"Transfer complete: {from_user} -> {to_user}")
    return True
