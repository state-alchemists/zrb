import asyncio
import random
from typing import List, Optional


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        if random.random() < self._failure_rate:
            return False
        async with self._lock:
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
        return True

    async def refund_last_charge(self, order_id: str) -> Optional[float]:
        """Refund the last charge for a given order_id."""
        async with self._lock:
            # Find the last charge for this order_id
            for i in range(len(self.charges) - 1, -1, -1):
                if self.charges[i]["order_id"] == order_id:
                    amount = self.charges[i]["amount"]
                    self.total_charged -= amount
                    self.charges.pop(i)
                    return amount
            return None
