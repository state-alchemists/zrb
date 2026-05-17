import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()

    async def check_stock(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        # Non-locking check used only for fast feedback; final decision is
        # protected by the lock in `decrement_if_possible`.
        return self._stock >= quantity

    async def decrement_if_possible(self, quantity: int) -> bool:
        """Atomically check and decrement stock.

        Ensures stock never goes below zero even under concurrency.
        """
        await asyncio.sleep(0.02)
        async with self._lock:
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def decrement(self, quantity: int) -> bool:
        # Preserve existing public method for compatibility by delegating
        # to the atomic implementation.
        return await self.decrement_if_possible(quantity)

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
