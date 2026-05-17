import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._processed_orders: set = set()
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        async with self._lock:
            if order_id in self._processed_orders:
                return False  # Already processed this order
            if order_id in [
                c["order_id"] for c in self.charges if c["amount"] == amount
            ]:
                return False  # Already charged this exact amount for this order
            self._processed_orders.add(order_id)

        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True

    async def refund(self, order_id: str) -> bool:
        """
        Refund a previously charged order. Returns True if found and refunded.
        """
        async with self._lock:
            for i, charge in enumerate(self.charges):
                if charge["order_id"] == order_id:
                    self.charges.pop(i)
                    self.total_charged -= charge["amount"]
                    return True
            return False
