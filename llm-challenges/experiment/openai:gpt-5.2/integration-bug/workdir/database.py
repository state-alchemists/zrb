import asyncio

class Database:
    """A very slow and unreliable database simulator."""
    def __init__(self):
        self.data = {
            "Alice": 100,
            "Bob": 100
        }

    async def get_balance(self, user):
        await asyncio.sleep(0.05)
        return self.data.get(user, 0)

    async def set_balance(self, user, amount):
        await asyncio.sleep(0.05)
        self.data[user] = amount
