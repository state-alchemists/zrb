import asyncio
from typing import Dict


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._lock = asyncio.Lock()
        self._reservations: Dict[str, int] = {}  # order_id -> quantity

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

    async def reserve_and_decrement(self, order_id: str, quantity: int) -> bool:
        """Atomically check stock and decrement if available."""
        async with self._lock:
            # Check if this order already has a reservation (idempotency)
            if order_id in self._reservations:
                return True  # Already reserved for this order
            if self._stock >= quantity:
                self._stock -= quantity
                self._reservations[order_id] = quantity
                return True
            return False

    async def release_reservation(self, order_id: str) -> None:
        """Release reserved inventory if payment fails."""
        async with self._lock:
            if order_id in self._reservations:
                self._stock += self._reservations[order_id]
                del self._reservations[order_id]

    @property
    def stock(self) -> int:
        return self._stock
