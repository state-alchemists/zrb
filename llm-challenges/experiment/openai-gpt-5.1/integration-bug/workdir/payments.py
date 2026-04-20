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
        """Charge an order once; idempotent per order_id.

        Returns True on successful (first) charge, False on failure or duplicate.
        """
        # Ensure idempotency and thread-safety across concurrent calls
        async with self._lock:
            # Prevent duplicate charges for the same order_id
            if any(c["order_id"] == order_id for c in self.charges):
                return False

            await asyncio.sleep(0.03)
            if random.random() < self._failure_rate:
                return False

            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            return True
