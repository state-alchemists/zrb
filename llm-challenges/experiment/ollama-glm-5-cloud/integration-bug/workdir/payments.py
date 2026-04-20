import asyncio
import random
from typing import List, Set


class PaymentGateway:
    def __init__(self, failure_rate: float = 0.25):
        self._failure_rate = failure_rate
        self.total_charged: float = 0.0
        self.charges: List[dict] = []
        self._processed_orders: Set[str] = set()

    async def charge(self, order_id: str, amount: float) -> bool:
        await asyncio.sleep(0.03)
        # Idempotency check - prevent duplicate charges for same order
        if order_id in self._processed_orders:
            # Return result of previous charge for this order
            for charge in self.charges:
                if charge["order_id"] == order_id:
                    return True
            return False
        
        if random.random() < self._failure_rate:
            self._processed_orders.add(order_id)
            return False
        
        self.total_charged += amount
        self.charges.append({"order_id": order_id, "amount": amount})
        self._processed_orders.add(order_id)
        return True
