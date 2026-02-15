import asyncio
from database import Database

db = Database()

async def transfer(from_user, to_user, amount):
    """Transfers money between users safely under concurrency.

    We acquire per-account locks in a deterministic order for the
    entire read-modify-write sequence, so no money is lost even with
    slow I/O and many concurrent transfers.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")

    # Acquire the two locks in a fixed global order to avoid deadlocks
    lock1, lock2 = db.get_transfer_locks(from_user, to_user)
    async with lock1:
        async with lock2:
            from_balance = await db.get_balance(from_user)
            if from_balance < amount:
                print(f"Insufficient funds for {from_user}")
                return False

            to_balance = await db.get_balance(to_user)

            await db.set_balance(from_user, from_balance - amount)
            await db.set_balance(to_user, to_balance + amount)

    print(f"Transfer complete: {from_user} -> {to_user}")
    return True
