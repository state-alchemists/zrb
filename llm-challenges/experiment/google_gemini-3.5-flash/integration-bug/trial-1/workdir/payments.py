import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._locks = {}
        self._successful_orders = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        if order_id not in self._locks:
            self._locks[order_id] = asyncio.Lock()

        async with self._locks[order_id]:
            if order_id in self._successful_orders:
                return True
            await asyncio.sleep(0.03)
            if random.random() < self._failure_rate:
                return False
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            self._successful_orders.add(order_id)
            return True
