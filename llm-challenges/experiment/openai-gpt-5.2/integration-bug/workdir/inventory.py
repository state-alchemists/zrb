import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()

    async def check_stock(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        async with self._lock:
            return self._stock >= quantity

    async def decrement(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        async with self._lock:
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def reserve(self, quantity: int) -> bool:
        """Atomically reserve (decrement) stock.

        This is identical to decrement() but explicit about intent: callers should
        reserve before charging to prevent oversells/ghost charges.
        """
        return await self.decrement(quantity)

    async def release(self, quantity: int) -> None:
        """Release previously reserved stock."""
        await self.increment(quantity)

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        async with self._lock:
            self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
