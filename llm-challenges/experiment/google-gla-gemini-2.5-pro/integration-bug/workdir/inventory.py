import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()

    async def reserve(self, quantity: int) -> bool:
        """Atomically check and decrement stock."""
        async with self._lock:
            await asyncio.sleep(0.02)  # Simulate I/O
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def restock(self, quantity: int) -> None:
        """Return items to stock."""
        async with self._lock:
            await asyncio.sleep(0.01)  # Simulate I/O
            self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
