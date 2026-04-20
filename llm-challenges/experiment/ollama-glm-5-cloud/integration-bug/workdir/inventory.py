import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()

    async def check_stock(self, quantity: int) -> bool:
        """Check if stock is available. Uses lock for consistency."""
        async with self._lock:
            await asyncio.sleep(0.02)
            return self._stock >= quantity

    async def decrement(self, quantity: int) -> bool:
        """Atomically decrement stock if available. Returns True if successful."""
        async with self._lock:
            await asyncio.sleep(0.02)
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def increment(self, quantity: int) -> None:
        """Increment stock (used for rollback on failed charges)."""
        async with self._lock:
            await asyncio.sleep(0.01)
            self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock