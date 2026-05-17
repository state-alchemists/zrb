import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._reserved: int = 0
        self._lock = asyncio.Lock()

    async def check_stock(self, quantity: int) -> bool:
        async with self._lock:
            await asyncio.sleep(0.02)
            return self._stock >= quantity

    async def decrement(self, quantity: int) -> bool:
        async with self._lock:
            await asyncio.sleep(0.02)
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def reserve(self, quantity: int) -> tuple[bool, int]:
        """
        Atomically reserve stock if available.
        Returns (success, reservation_id) where reservation_id is a non-zero int on success.
        """
        async with self._lock:
            await asyncio.sleep(0.02)
            if self._stock >= quantity:
                self._stock -= quantity
                self._reserved += quantity
                return (True, 1)
            return (False, 0)

    async def release_reservation(self, quantity: int) -> None:
        """
        Release a reservation (e.g., after payment failure) - restores stock.
        """
        async with self._lock:
            await asyncio.sleep(0.01)
            if self._reserved >= quantity:
                self._reserved -= quantity
                self._stock += quantity

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock
