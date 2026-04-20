import asyncio
import threading


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = threading.Lock()

    async def check_stock(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        with self._lock:
            return self._stock >= quantity

    async def decrement(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        with self._lock:
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        with self._lock:
            self._stock += quantity

    @property
    def stock(self) -> int:
        with self._lock:
            return self._stock
