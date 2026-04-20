import asyncio


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()

    async def reserve(self, quantity: int) -> bool:
        """Atomically reserve stock if available.

        This prevents race conditions between concurrent check/dec
        operations and guarantees stock never goes below zero.
        """
        async with self._lock:
            await asyncio.sleep(0.02)
            if self._stock >= quantity:
                self._stock -= quantity
                return True
            return False

    async def confirm(self, quantity: int) -> None:
        """Confirm a reservation.

        For this simple model, reservations are effected immediately in
        `reserve`, so confirmation is a no-op. The method exists to
        mirror a two‑phase pattern if later extended.
        """
        # No extra work required once reserved.
        return None

    async def release(self, quantity: int) -> None:
        """Release previously reserved stock (compensation)."""
        async with self._lock:
            await asyncio.sleep(0.01)
            self._stock += quantity

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

    @property
    def stock(self) -> int:
        return self._stock
