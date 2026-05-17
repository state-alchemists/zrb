import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []

    def has_charged(self, order_id: str) -> bool:
        return any(c["order_id"] == order_id for c in self.charges)

    async def refund(self, order_id: str, amount: float) -> None:
        # In a real scenario, this would contact the gateway.
        # For simulation, we just subtract the charge.
        self.total_charged -= amount
        self.charges = [c for c in self.charges if c["order_id"] != order_id]

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True
