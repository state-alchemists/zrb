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
        async with self._lock:
            await asyncio.sleep(0.03)
            # Prevent duplicate charges for the same order_id
            if any(charge["order_id"] == order_id for charge in self.charges):
                print(f"PaymentGateway: Duplicate charge attempt for order {order_id}")
                return False

            if random.random() < self._failure_rate:
                return False
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            return True
