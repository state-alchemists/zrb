import asyncio

class Database:
    """A very slow and unreliable database simulator."""
    def __init__(self):
        self.data = {
            "Alice": 100,
            "Bob": 100
        }
        # Simple per-user locks to avoid race conditions
        self._locks = {}

    def _get_lock(self, user: str) -> asyncio.Lock:
        if user not in self._locks:
            self._locks[user] = asyncio.Lock()
        return self._locks[user]

    def get_transfer_locks(self, user1: str, user2: str):
        """Return two locks for a transfer, always in a fixed order.

        This prevents deadlocks when multiple concurrent transfers
        involve overlapping accounts.
        """
        # Ensure deterministic ordering by user name
        first, second = sorted([user1, user2])
        return self._get_lock(first), self._get_lock(second)

    async def get_balance(self, user):
        await asyncio.sleep(0.05)
        return self.data.get(user, 0)

    async def set_balance(self, user, amount):
        await asyncio.sleep(0.05)
        self.data[user] = amount
