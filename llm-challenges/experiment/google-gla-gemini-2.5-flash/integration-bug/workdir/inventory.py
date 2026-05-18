import asyncio
from asyncio import Lock


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = Lock()

    async def check_and_decrement(self, quantity: int) -> bool:
        async with self._lock:
            await asyncio.sleep(0.02)  # Simulate async I/O
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def decrement(self, quantity: int) -> bool:
        # This method is no longer used directly for atomic operations.
        # check_and_decrement should be used instead.
        # Keeping it for interface compatibility, but it will not be called by checkout.
        await asyncio.sleep(0.02)
        if self._stock >= quantity:
            self._stock -= quantity
            return True
        return False

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
