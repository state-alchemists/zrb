import asyncio
from database import Database

db = Database()

# Locks to prevent race conditions during concurrent transfers
_account_locks = {}

async def _get_account_lock(user):
    """Get or create a lock for a specific user account."""
    if user not in _account_locks:
        _account_locks[user] = asyncio.Lock()
    return _account_locks[user]

async def transfer(from_user, to_user, amount):
    """
    Transfers money between users atomically.
    Uses locks to prevent race conditions during concurrent transfers.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")

    # Acquire locks in consistent order to prevent deadlocks
    users = sorted([from_user, to_user])
    async with await _get_account_lock(users[0]):
        async with await _get_account_lock(users[1]):
            # Check balance inside the lock to prevent race conditions
            from_balance = await db.get_balance(from_user)
            if from_balance < amount:
                print(f"Insufficient funds for {from_user}")
                return False

            # Get destination balance
            to_balance = await db.get_balance(to_user)

            # Perform transfer atomically
            await db.set_balance(from_user, from_balance - amount)
            await db.set_balance(to_user, to_balance + amount)

    print(f"Transfer complete: {from_user} -> {to_user}")
    return True
