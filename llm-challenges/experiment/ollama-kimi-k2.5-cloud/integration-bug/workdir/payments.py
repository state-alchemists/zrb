import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self._lock = asyncio.Lock()
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._charged_order_ids: Set[str] = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        async with self._lock:
            if order_id in self._charged_order_ids:
                return False
            self._charged_order_ids.add(order_id)

        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False

        async with self._lock:
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
        return True
