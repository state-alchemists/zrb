import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._lock = asyncio.Lock()
        self._charged_orders = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        async with self._lock:
            if order_id in self._charged_orders:
                # Idempotency: already charged.
                return True
            if random.random() < self._failure_rate:
                return False
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            self._charged_orders.add(order_id)
            return True

    async def is_charged(self, order_id: str) -> bool:
        async with self._lock:
            return order_id in self._charged_orders

    async def refund(self, order_id: str) -> bool:
        """Best-effort refund for this mock gateway.

        Removes the recorded charge and total if the order was previously charged.
        """
        async with self._lock:
            if order_id not in self._charged_orders:
                return False
            # Find the first matching charge record.
            for i, c in enumerate(self.charges):
                if c.get("order_id") == order_id:
                    self.total_charged -= float(c.get("amount", 0.0))
                    self.charges.pop(i)
                    break
            self._charged_orders.remove(order_id)
            return True
