import asyncio
from database import Database

db = Database()

# In-memory lock to make transfers atomic in this simulator.
# Real systems should use database transactions/row locks.
_db_lock = asyncio.Lock()

async def transfer(from_user, to_user, amount):
    """Transfers money between users.

    Previously, this function performed a read-then-write sequence without any
    synchronization, causing lost updates during concurrent transfers.
    This simulator fix makes the transfer atomic using a single lock.
    """
    if amount <= 0:
        return False

    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")

    async with _db_lock:
        # Check balance (inside lock)
        from_balance = await db.get_balance(from_user)
        if from_balance < amount:
            print(f"Insufficient funds for {from_user}")
            return False

        # Get destination balance (inside lock)
        to_balance = await db.get_balance(to_user)

        # Perform transfer atomically
        await db.set_balance(from_user, from_balance - amount)
        await db.set_balance(to_user, to_balance + amount)

    print(f"Transfer complete: {from_user} -> {to_user}")
    return True
