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

    async def reserve_stock(self, quantity: int) -> bool:
        """Atomic check and decrement - prevents overselling."""
        async with self._lock:
            await asyncio.sleep(0.01)  # Simulate I/O latency
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def cancel_reservation(self, quantity: int) -> None:
        """Release reserved stock (rollback)."""
        async with self._lock:
            await asyncio.sleep(0.01)  # Simulate I/O latency
            self._stock += quantity

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
