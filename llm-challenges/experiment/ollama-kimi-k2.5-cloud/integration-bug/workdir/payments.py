import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._charged_order_ids: Set[str] = set()
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        async with self._lock:
            # Idempotency: prevent duplicate charges for same order
            if order_id in self._charged_order_ids:
                return False
            if random.random() < self._failure_rate:
                return False
            self._charged_order_ids.add(order_id)
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            return True

    async def refund(self, order_id: str, amount: float) -> bool:
        """Reverse a charge for the given order_id."""
        await asyncio.sleep(0.02)
        async with self._lock:
            if order_id not in self._charged_order_ids:
                return False
            self._charged_order_ids.discard(order_id)
            self.total_charged -= amount
            # Remove the charge record
            self.charges = [c for c in self.charges if c["order_id"] != order_id]
            return True
