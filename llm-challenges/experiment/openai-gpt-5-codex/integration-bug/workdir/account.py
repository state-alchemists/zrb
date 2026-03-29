import asyncio
from database import Database

db = Database()

async def transfer(from_user, to_user, amount):
    """
    Transfers money between users.
    TODO: This seems to have issues when many people transfer at once.
    """
    print(f"Starting transfer: {from_user} -> {to_user} (${amount})")
    
    # Check balance
    from_balance = await db.get_balance(from_user)
    if from_balance < amount:
        print(f"Insufficient funds for {from_user}")
        return False

    # Get destination balance
    to_balance = await db.get_balance(to_user)

    # Perform transfer
    # (Race condition happens here because we read then write later)
    await db.set_balance(from_user, from_balance - amount)
    await db.set_balance(to_user, to_balance + amount)
    
    print(f"Transfer complete: {from_user} -> {to_user}")
    return True
