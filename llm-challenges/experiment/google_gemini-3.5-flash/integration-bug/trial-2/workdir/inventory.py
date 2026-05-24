import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def check_stock(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        async with self._get_lock():
            return self._stock >= quantity

    async def decrement(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        async with self._get_lock():
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        async with self._get_lock():
            self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock

    async def reserve(self, quantity: int) -> bool:
        async with self._get_lock():
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False
