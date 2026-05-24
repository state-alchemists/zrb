import asyncio
import uuid


class Inventory:
    def __init__(self, stock: int):
        self._stock = stock
        self._reservations: dict[str, int] = {}

    async def reserve_stock(self, quantity: int) -> str | None:
        await asyncio.sleep(0.02)
        if self._stock >= quantity:
            self._stock -= quantity
            reservation_id = str(uuid.uuid4())
            self._reservations[reservation_id] = quantity
            return reservation_id
        return None

    async def cancel_reservation(self, reservation_id: str) -> None:
        await asyncio.sleep(0.01)
        if reservation_id in self._reservations:
            self._stock += self._reservations.pop(reservation_id)

    async def decrement_reserved(self, reservation_id: str) -> bool:
        await asyncio.sleep(0.01)
        if reservation_id in self._reservations:
            del self._reservations[reservation_id]
            return True
        return False

    async def increment(self, quantity: int) -> None:
        await asyncio.sleep(0.01)
        self._stock += quantity

    @property
    def stock(self) -> int:
        return self._stock

