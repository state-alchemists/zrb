import asyncio


class Database:
    """A very slow and unreliable database simulator."""
    def __init__(self):
        self.data = {
            "Alice": 100,
            "Bob": 100
        }
        self.lock = asyncio.Lock()

    async def get_balance(self, user):
        await asyncio.sleep(0.05)
        return self.data.get(user, 0)

    async def set_balance(self, user, amount):
        await asyncio.sleep(0.05)
        self.data[user] = amount

    async def transfer(self, from_user, to_user, amount):
        async with self.lock:
            from_balance = await self.get_balance(from_user)
            if from_balance < amount:
                return False

            to_balance = await self.get_balance(to_user)
            await self.set_balance(from_user, from_balance - amount)
            await self.set_balance(to_user, to_balance + amount)
            return True
