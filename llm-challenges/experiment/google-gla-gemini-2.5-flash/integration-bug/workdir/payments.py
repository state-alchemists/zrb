import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._lock = asyncio.Lock()  # Add a lock for synchronization

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        async with self._lock:
            if random.random() < self._failure_rate:
                return False
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            return True

    async def refund(self, order_id: str, amount: float) -> None:
        await asyncio.sleep(0.03)
        async with self._lock:
            self.total_charged -= amount
            # Remove the charge from the list. Assuming unique order_id for simplicity.
            self.charges = [c for c in self.charges if not (c["order_id"] == order_id and c["amount"] == amount)]
