import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._refunded: List[str] = []

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True

    async def refund(self, order_id: str, amount: float) -> None:
        """Reverse a charge. Idempotent — safe to call multiple times."""
        await asyncio.sleep(0.01)
        if order_id not in self._refunded:
            self.total_charged -= amount
            self.charges = [c for c in self.charges if c["order_id"] != order_id]
            self._refunded.append(order_id)
