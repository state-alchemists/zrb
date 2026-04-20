import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()

    async def check_stock(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        return self._stock >= quantity

    async def decrement(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        if self._stock >= quantity:
            self._stock -= quantity
            return True
        return False

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        self._stock += quantity

    async def reserve(self, quantity: int) -> bool:
        """Atomically check and decrement stock if available."""
        async with self._lock:
            await asyncio.sleep(0.02)  # Simulate processing time
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    @property
    def stock(self) -> int:
        return self._stock
