import asyncio
import random
from typing import List


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
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        return True

    async def void_charge(self, order_id: str) -> bool:
        """Remove a charge from the gateway. Returns True if charge exists and is voided."""
        async with self._lock:
            for i, charge in enumerate(self.charges):
                if charge["order_id"] == order_id:
                    self.total_charged -= charge["amount"]
                    self.charges.pop(i)
                    return True
            return False
