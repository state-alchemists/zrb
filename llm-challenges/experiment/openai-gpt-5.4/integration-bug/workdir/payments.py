import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._lock = asyncio.Lock()
        self._charged_orders: set[str] = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        async with self._lock:
            if order_id in self._charged_orders:
                return False
            if random.random() < self._failure_rate:
                return False
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            self._charged_orders.add(order_id)
            return True
