import asyncio
import threading


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._reserved = 0
        self._lock = threading.Lock()

    async def check_stock(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        return self._stock >= quantity

    async def decrement(self, quantity: int) -> bool:
        await asyncio.sleep(0.02)
        if self._stock >= quantity:
            self._stock -= quantity
            return True
        return False

    async def check_and_reserve(self, quantity: int) -> bool:
        """Atomically check and reserve stock."""
        await asyncio.sleep(0.02)
        with self._lock:
            if self._stock >= quantity:
                self._stock -= quantity
                self._reserved += quantity
                return True
            return False

    async def finalize_reserve(self, quantity: int) -> bool:
        """Confirm the reserved stock was actually used."""
        with self._lock:
            if self._reserved >= quantity:
                self._reserved -= quantity
                return True
            return False

    async def undo_reserve(self, quantity: int) -> None:
        """Undo a reservation (restore stock + reserved)."""
        await asyncio.sleep(0.01)
        with self._lock:
            self._stock += quantity
            self._reserved -= quantity
            if self._reserved < 0:
                self._reserved = 0

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        with self._lock:
            self._stock += quantity

    @property
    def stock(self) -> int:
        with self._lock:
            return self._stock
