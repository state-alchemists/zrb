import asyncio
from database import Database

db = Database()
user_locks = {}

async def _get_user_lock(user):
    if user not in user_locks:
        user_locks[user] = asyncio.Lock()
    return user_locks[user]

async def transfer(from_user, to_user, amount):
    """
    Transfers money between users.
    This has been fixed to prevent race conditions during concurrent transfers.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")

    # Acquire locks for both users in a consistent order to prevent deadlocks
    # Sort names alphabetically to ensure consistent lock acquisition order
    locked_users = sorted([from_user, to_user])
    lock1 = await _get_user_lock(locked_users[0])
    lock2 = await _get_user_lock(locked_users[1])

    async with lock1:
        async with lock2:
            # Check balance
            from_balance = await db.get_balance(from_user)
            if from_balance < amount:
                print(f"Insufficient funds for {from_user}")
                return False

            # Get destination balance
            to_balance = await db.get_balance(to_user)

            # Perform transfer
            await db.set_balance(from_user, from_balance - amount)
            await db.set_balance(to_user, to_balance + amount)
            
            print(f"Transfer complete: {from_user} -> {to_user}")
            return True
