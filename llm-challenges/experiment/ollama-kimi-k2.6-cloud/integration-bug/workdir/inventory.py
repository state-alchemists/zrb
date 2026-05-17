import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()
        self._reserved: dict[str, int] = {}

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

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        async with self._lock:
            self._stock += quantity

    async def reserve(self, order_id: str, quantity: int) -> bool:
        """Atomically reserve inventory for an order.

        Returns True if the reservation succeeds (or was already held for this
        order_id). Returns False if insufficient stock remains.
        """
        await asyncio.sleep(0.02)
        async with self._lock:
            if order_id in self._reserved:
                return True
            if self._stock >= quantity:
                self._stock -= quantity
                self._reserved[order_id] = quantity
                return True
            return False

    async def release(self, order_id: str) -> None:
        """Release a prior reservation, restoring stock."""
        await asyncio.sleep(0.01)
        async with self._lock:
            if order_id in self._reserved:
                self._stock += self._reserved.pop(order_id)

    @property
    def stock(self) -> int:
        return self._stock
