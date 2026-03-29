import asyncio

class Database:
    """A very slow and unreliable database simulator."""
    def __init__(self):
        self.data = {
            "Alice": 100,
            "Bob": 100
        }
        self._lock = asyncio.Lock()

    async def get_balance(self, user):
        async with self._lock:
            await asyncio.sleep(0.05)
            return self.data.get(user, 0)

    async def set_balance(self, user, amount):
        async with self._lock:
            await asyncio.sleep(0.05)
            self.data[user] = amount

    async def transfer(self, from_user, to_user, amount):
        """Atomically transfer money between users. Returns True on success."""
        async with self._lock:
            from_balance = self.data.get(from_user, 0)
            if from_balance < amount:
                return False

            to_balance = self.data.get(to_user, 0)

            # Simulate slow database writes
            await asyncio.sleep(0.05)
            self.data[from_user] = from_balance - amount

            await asyncio.sleep(0.05)
            self.data[to_user] = to_balance + amount

            return True
