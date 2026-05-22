import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self._charged_ids: Set[str] = set()
        self.total_charged: float = 0.0
        self.charges: List[dict] = []

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        # Idempotency guard — no order charged more than once
        if order_id in self._charged_ids:
            return False
        if random.random() < self._failure_rate:
            return False
        self._charged_ids.add(order_id)
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True
