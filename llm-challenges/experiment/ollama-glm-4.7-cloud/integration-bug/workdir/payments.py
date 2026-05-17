import asyncio
import random
from typing import List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._charged_order_ids: set = set()
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False

        async with self._lock:
            if order_id in self._charged_order_ids:
                return False
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            self._charged_order_ids.add(order_id)
            return True

    async def refund(self, order_id: str) -> bool:
        """Refund a charge for the given order_id. Returns True if refunded."""
        await asyncio.sleep(0.02)
        async with self._lock:
            for i, charge in enumerate(self.charges):
                if charge["order_id"] == order_id:
                    self.total_charged -= charge["amount"]
                    self.charges.pop(i)
                    self._charged_order_ids.remove(order_id)
                    return True
            return False
