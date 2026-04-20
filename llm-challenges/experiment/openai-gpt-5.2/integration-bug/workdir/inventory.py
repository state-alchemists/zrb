import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()

    async def check_stock(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        return self._stock >= quantity

    async def decrement(self, quantity: int) -> bool:
        # Backwards-compatible, but now atomic with respect to other updates.
        await asyncio.sleep(0.02)
        async with self._lock:
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def reserve(self, quantity: int) -> bool:
        """Atomically reserve stock.

        If this returns True, the caller MUST eventually call either:
        - confirm_reservation(quantity)  (deliver)
        - release_reservation(quantity)  (rollback)
        """
        await asyncio.sleep(0.0)
        async with self._lock:
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def release_reservation(self, quantity: int) -> None:
        await asyncio.sleep(0.0)
        async with self._lock:
            self._stock += quantity

    async def confirm_reservation(self, quantity: int) -> None:
        # No-op in this simplified model (stock was already decremented).
        await asyncio.sleep(0.0)
        return None

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
