import asyncio
from database import Database

db = Database()
locks = {}

async def transfer(from_user, to_user, amount):
    """
    Transfers money between users with lock mechanism.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")

    # Lock for both accounts
    f_lock, t_lock = (locks.setdefault(from_user, asyncio.Lock()), locks.setdefault(to_user, asyncio.Lock()))
    async with f_lock, t_lock:
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
