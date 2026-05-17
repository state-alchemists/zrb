import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock

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
        """Atomically reserve stock. Returns True if reserved, False if insufficient."""
        if self._stock >= quantity:
            self._stock -= quantity
            return True
        return False

    async def release(self, quantity: int) -> None:
        """Release previously reserved stock back (e.g. after payment failure)."""
        self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
