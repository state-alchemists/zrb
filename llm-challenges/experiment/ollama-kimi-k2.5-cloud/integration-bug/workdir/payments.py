import asyncio
import random
from typing import Dict, List


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._charge_ids: set[str] = set()
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        """Idempotent charge. Returns True if newly charged or already charged."""
        async with self._lock:
            if order_id in self._charge_ids:
                return True
            await asyncio.sleep(0.03)
            if random.random() < self._failure_rate:
                return False
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            self._charge_ids.add(order_id)
            return True

    async def refund(self, order_id: str) -> bool:
        """Refund a charge for the given order_id. Returns True if refunded."""
        async with self._lock:
            await asyncio.sleep(0.02)
            if order_id not in self._charge_ids:
                return False
            self._charge_ids.discard(order_id)
            for i, charge in enumerate(self.charges):
                if charge["order_id"] == order_id:
                    self.total_charged -= charge["amount"]
                    self.charges.pop(i)
                    return True
            return False
