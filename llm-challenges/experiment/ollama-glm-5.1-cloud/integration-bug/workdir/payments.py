import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []

    def _find_charge(self, order_id: str):
        return next((c for c in self.charges if c["order_id"] == order_id), None)

    async def charge(self, order_id: str, amount: float) -> bool:
        existing = self._find_charge(order_id)
        if existing:
            return True
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True
