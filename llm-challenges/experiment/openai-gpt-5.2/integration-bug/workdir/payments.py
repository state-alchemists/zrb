import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._charged_order_ids = set()
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        # Idempotent by order_id: never charge the same order twice.
        async with self._lock:
            if order_id in self._charged_order_ids:
                return True

        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False

        async with self._lock:
            if order_id in self._charged_order_ids:
                return True
            self._charged_order_ids.add(order_id)
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            return True
