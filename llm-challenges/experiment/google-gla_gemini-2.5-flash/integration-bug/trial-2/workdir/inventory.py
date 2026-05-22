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

    async def reserve(self, quantity: int) -> bool:
        """Atomically check stock and decrement — no await between check and mutation.

        Unlike the separate check_stock → decrement sequence, this eliminates
        the TOCTOU race that causes overselling under concurrency.
        """
        if self._stock >= quantity:
            self._stock -= quantity
            await asyncio.sleep(0.02)
            return True
        await asyncio.sleep(0.02)
        return False

    async def release(self, quantity: int) -> None:
        """Roll back a previous reserve when the downstream operation (charge) fails."""
        self._stock += quantity
        await asyncio.sleep(0.01)

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
