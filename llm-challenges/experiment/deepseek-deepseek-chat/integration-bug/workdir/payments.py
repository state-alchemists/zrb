import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._processed_orders: Set[str] = set()
        self._lock = asyncio.Lock()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        
        if random.random() < self._failure_rate:
            return False
        
        async with self._lock:
            # Check for duplicate order_id atomically
            if order_id in self._processed_orders:
                # Already processed this order - idempotent success
                return True
            self._processed_orders.add(order_id)
            self.total_charged += amount
            self.charges.append({"order_id": order_id, "amount": amount})
            return True
