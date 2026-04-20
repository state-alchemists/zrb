import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._charged_order_ids: Set[str] = set()
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        async with self._lock:
            # Idempotency: prevent duplicate charges for same order_id
            if order_id in self._charged_order_ids:
                return True  # Already charged successfully

        await asyncio.sleep(0.03)

        async with self._lock:
            # Recheck after I/O in case of concurrent calls
            if order_id in self._charged_order_ids:
                return True

            if random.random() < self._failure_rate:
                return False

            self._charged_order_ids.add(order_id)
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            return True
